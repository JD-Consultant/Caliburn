"""The existing advisor's three schema-first JD capabilities."""
from copy import deepcopy
from contextvars import ContextVar
import json
from uuid import UUID, uuid5, NAMESPACE_URL
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command
from jsonschema import ValidationError as SchemaValidationError
from analysis_agent.jd_contract import (SCHEMA_PATH, validate, PROFILE, _ref, revision_ref,
    operation_ref, outcome_to_wire, request_digest, read_failure_to_wire)
from analysis_agent.jd_types import JdScope, JdReadQuery, JdChangeQuery, JdEditIntent, JdReadView
from analysis_agent.jd_references import IssuedReferences, elements, source_refs, validate_sources

NAMES = {'jd_read':'JdReadModelInput','jd_edit':'JdEditModelInput','jd_change_read':'JdChangeReadModelInput'}


def model_schema(name):
    definitions=json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))['$defs']
    root=deepcopy(definitions[NAMES[name]])
    required={}
    def visit(value):
        if isinstance(value,dict):
            if '$ref' in value:
                key=value['$ref'].split('/')[-1]
                if key not in required:
                    required[key]=deepcopy(definitions[key]); visit(required[key])
            for item in value.values(): visit(item)
        elif isinstance(value,list):
            for item in value: visit(item)
    visit(root)
    if required: root['$defs']=required
    return root


def _jd_message_projection(messages, result_ids):
    """Exact request-local result bodies and their visible AI call pairing."""
    results=[m for m in messages if isinstance(m,ToolMessage) and m.id in result_ids]
    calls={m.tool_call_id for m in results}
    return deepcopy({
        'results':[m.model_dump() for m in results],
        'calls':[{'message_id':m.id,'call':call} for m in messages if isinstance(m,AIMessage)
            for call in m.tool_calls if call['id'] in calls],
    })


class JdSessionState(AgentState):
    jd_bindings: dict
    jd_refs: dict
    jd_sources: dict
    jd_results: dict
    jd_turn_id: str
    jd_binding: dict | None
    jd_selection: dict | None
    jd_last_model_view: dict | None
    jd_turn_notice: dict | None
    jd_pending_operation: dict | None


class JdToolSession(AgentMiddleware):
    state_schema=JdSessionState

    def __init__(self, service, source, *, page_size=64, cancel=None, source_read_tools=(), native_calls=None):
        from analysis_agent.jd_engine import JdNativeCalls
        self.native_calls = native_calls if native_calls is not None else JdNativeCalls()
        self.stopped_proof = None
        self.source_read_tools=tuple(t for t in source_read_tools if t.name=="read_conversation")
        self.cancel=cancel
        self.model_preparation=ContextVar("jd_model_preparation",default=None)
        if page_size < 1: raise ValueError('Positive page size required')
        self.service,self.source,self.scope,self.page_size=service,source,JdScope(source.document_id),page_size
        def make(name):
            schema=model_schema(name)
            @tool(name,description=schema['description'],args_schema=schema)
            def execute(runtime: ToolRuntime, **kwargs) -> Command:
                return self.execute(name,kwargs,runtime.state,runtime.tool_call_id)
            return execute
        self.tools=tuple(make(name) for name in NAMES)
        self.read_tools=(self.tools[0],self.tools[2])

    def _scope(self, config):
        if config['configurable']['thread_id'] != self.scope.document_id:
            raise ValueError('JD session belongs to another document')

    def before_agent(self,state,runtime):
        from langgraph.config import get_config
        self._scope(get_config())
        current=next(m for m in reversed(state['messages']) if isinstance(m,HumanMessage))
        if state.get('jd_turn_id')==current.id: return None
        source=self.source.capture_input(current.id)
        previous=state.get('jd_last_model_view')
        if previous and previous.get('document')!=self.scope.document_id:
            raise ValueError('JD model view belongs to another document')
        if previous and not any(isinstance(m,AIMessage) and m.id==previous.get('response_id')
                and m.response_metadata.get('status')=='completed' for m in state['messages']):
            previous=None
        if state.get('jd_pending_operation') or any(not b.get('closed') for b in state.get('jd_bindings',{}).values()):
            from analysis_agent.publication import PublicationUncertain
            raise PublicationUncertain('Prior JD calls must close before a new input')
        return {'jd_last_model_view':previous,'jd_turn_id':current.id,'jd_binding':None,'jd_turn_notice':None,'jd_bindings':{},
            'jd_refs':state.get('jd_refs',{}),'jd_results':state.get('jd_results',{}),
            'jd_sources':{**state.get('jd_sources',{}),source:{'current_input':current.id}}}

    def after_model(self,state,runtime):
        message=state['messages'][-1]
        if not isinstance(message,AIMessage) or message.response_metadata.get('status')!='completed':
            raise ValueError('Incomplete JD model response')
        if len(message.tool_calls)>1: raise ValueError('Parallel JD calls are unsupported')
        if not message.tool_calls or message.tool_calls[0]['name'] not in NAMES: return None
        call=message.tool_calls[0]
        if not message.id or not call.get('id'):
            raise ValueError('JD call requires saved AI message and tool call identities')
        identity=[self.scope.document_id,state['jd_turn_id'],message.id,call['id']]
        binding={'document':self.scope.document_id,'input':state['jd_turn_id'],'message':message.id,
            'call':call['id'],'name':call['name'],'args':deepcopy(call['args']),
            'operation':str(uuid5(NAMESPACE_URL,'jd:'+json.dumps(identity)))}
        if call['name']=='jd_edit':
            try:
                validate(NAMES[call['name']],call['args'])
                refs=IssuedReferences(self.scope,state.get('jd_refs',{}),input_id=state.get('jd_turn_id'))
                base,commands=self._resolve(call['args'],refs)
                validate_sources(source_refs(call['args']),state.get('jd_sources',{}),self.source)
                binding.update(base=str(base),commands=commands,digest=request_digest(self.scope,base,commands,'ai'))
            except (ValueError, SchemaValidationError) as exc:
                binding['invalid']=str(exc).split('\n')[0][:300]
        return {'jd_binding':binding,'jd_bindings':{**state.get('jd_bindings',{}),call['id']:binding}}

    def before_model(self,state,runtime):
        if state.get("jd_pending_operation") or not self.native_calls.quiescent:
            from analysis_agent.publication import PublicationUncertain
            raise PublicationUncertain("JD operation requires reconciliation before another model request")
        from analysis_agent.jd_context import prepare_notice
        refs=IssuedReferences(self.scope,state.get("jd_refs",{}))
        _,_,basis=prepare_notice(self,state,state["messages"],refs)
        return {"jd_refs":refs.bindings,"jd_turn_notice":basis}

    def wrap_model_call(self,request,handler):
        replacements={id(t):{'type':'function','name':t.name,'description':t.description,
            'parameters':model_schema(t.name),'strict':False} for t in self.tools}
        for item in request.tools:
            name=item.name if hasattr(item,'name') else item.get('name',item.get('function',{}).get('name'))
            if name in NAMES and id(item) not in replacements:
                raise ValueError('JD names are reserved for original factory tools')
        from analysis_agent.jd_context import prepare_notice, encoded, CONTEXT_GUIDANCE
        from langchain_core.messages import SystemMessage
        refs=IssuedReferences(self.scope,request.state.get('jd_refs',{}))
        payload,manifest,basis=prepare_notice(self,request.state,request.messages,refs)
        system=request.system_message.content if request.system_message else ''
        blocks=[{'type':'text','text':system}] if isinstance(system,str) else list(system)
        blocks.append({'type':'text','text':CONTEXT_GUIDANCE})
        notice=HumanMessage(encoded(payload))
        prepared=request.override(tools=[replacements.get(id(t),t) for t in request.tools],
            system_message=SystemMessage(content=blocks),messages=[*request.messages,notice])
        # Request-local expectation, never a second durable view owner.
        token=self.model_preparation.set((deepcopy(list(replacements.values())),notice.model_dump(),manifest,basis,refs,
            _jd_message_projection(request.messages,manifest['visible_jd_results'])))
        try:
            return handler(prepared)
        finally:
            self.model_preparation.reset(token)

    def confirm_model_response(self,response,manifest,basis,refs):
        from langchain.agents.middleware.types import ExtendedModelResponse
        inner=response.model_response if isinstance(response,ExtendedModelResponse) else response
        message=inner.result[-1]
        if not isinstance(message,AIMessage) or message.response_metadata.get('status')!='completed' or not message.id:
            raise ValueError('Unconfirmed response cannot advance JD model view')
        manifest['response_id']=message.id
        update={}
        if isinstance(response,ExtendedModelResponse) and response.command:
            command=response.command
            if command.goto or command.resume or command.graph:
                raise ValueError('JD model view requires a state-only command')
            update.update(command.update or {})
        update.update(jd_last_model_view=manifest,jd_refs=refs.bindings,jd_turn_notice=basis)
        return ExtendedModelResponse(inner,Command(update=update))

    def wrap_tool_call(self,request,handler):
        self._scope(request.runtime.config)
        if request.tool_call['name'] in NAMES:
            expected=next(t for t in self.tools if t.name==request.tool_call['name'])
            if request.tool is not expected: raise ValueError('JD tool factory identity mismatch')
        observed=[]
        if any(request.tool is t for t in self.source_read_tools):
            with self.source.observe_reads() as observed:
                result=handler(request)
        else:
            result=handler(request)
        # A successful existing source read is a checkpointed acquisition; a
        # parseable handle or Memory guide alone is not original source reading.
        if (any(request.tool is t for t in self.source_read_tools) and isinstance(result,ToolMessage)
                and result.status=='success'):
            payload=json.loads(result.content)
            reference=payload.get('reference')
            if reference and not any(all(payload.get(k)==v for k,v in original.items()) for original in observed):
                raise ValueError('JD source acquisition requires the actual owner read result')
            if reference and any(s.get('role')=='user' for s in payload.get('segments',[])):
                prior=request.state.get('jd_sources',{})
                # Reading an already issued current-input window must not erase
                # its saved-input authority; that window is not a closed turn yet.
                issued={**prior,reference:{**prior.get(reference,{}),'tool_call':request.tool_call['id']}}
                return Command(update={'messages':[result],'jd_sources':issued})
        return result

    def _revision(self,refs,id):
        return refs.issue('revision',ref=revision_ref(self.scope,id),revision=str(id),access='read_only')

    def _change(self,refs,outcome):
        wire=outcome_to_wire(outcome)
        ref=refs.issue('change',ref=wire['change_ref'],operation=str(outcome.operation_id),
            before=str(outcome.base_id),after=str(outcome.result_id),access='read_only')
        self._revision(refs,outcome.base_id); self._revision(refs,outcome.result_id)
        return ref

    def _target(self,refs,revision,node,access,*,supplied):
        # Acquisition is encoded in the issued identity, so a navigation-only
        # relationship ref never silently gains content-read authority.
        return refs.issue('target',revision=str(revision.id),target=node['id'],access=access,
            content_supplied=supplied,element_type=node['type'],input=refs.input_id)

    def _read(self,args,state,refs):
        kind,access,query,offset='current','current_base',JdReadQuery(),0
        if 'continuation_ref' in args:
            page=refs.require(args['continuation_ref'],'read_page')
            kind,access,offset=page['read_kind'],page['access'],page['offset']
            query=JdReadQuery(UUID(page['revision']),page.get('target'),page.get('range'))
        elif 'revision_ref' in args:
            r=refs.require(args['revision_ref'],'revision'); kind,access='history','read_only'
            query=JdReadQuery(UUID(r['revision']))
        elif 'target_ref' in args:
            r=refs.require(args['target_ref'],'target'); kind,access='target',r['access']
            query=JdReadQuery(UUID(r['revision']),r['target'])
        elif 'selection_ref' in args:
            r=refs.require(args['selection_ref'],'selection'); kind,access='selection',r['access']
            query=JdReadQuery(UUID(r['revision']),selection=r['range'])
        view=self.service.read(self.scope,query, cancel=self.cancel, native_calls=self.native_calls)
        if view.status!='ok': return read_failure_to_wire(view)
        revision=view.revision; fragment=view.fragment[offset:offset+self.page_size]
        index={n['id']:n for n in elements(revision.value)}
        targets=[]
        for node in elements(fragment):
            entry={'target_ref':self._target(refs,revision,node,access,supplied=kind!='selection'),'element':node,'access':access}
            if node['type']=='jd_task':
                for field in ('knowledge','skill'):
                    entry[field+'_refs']=[self._target(refs,revision,index[id],access,supplied=False) for id in node.get(field+'_ids',[])]
            if node['type'] in ('jd_knowledge','jd_skill'):
                field='knowledge_ids' if node['type']=='jd_knowledge' else 'skill_ids'
                entry['used_by_task_refs']=[self._target(refs,revision,n,access,supplied=False) for n in index.values() if n['type']=='jd_task' and node['id'] in n.get(field,[])]
            targets.append(entry)
        continuation=None
        if offset+len(fragment)<len(view.fragment):
            continuation=refs.issue('read_page',revision=str(revision.id),read_kind=kind,access=access,
                offset=offset+len(fragment),target=query.target_id,range=query.selection)
        selection=None
        capture=state.get('jd_selection')
        if kind=='current' and capture and capture.get('input')==state['jd_turn_id'] and capture['revision']==str(revision.id):
            node=index[capture['target']]
            target=self._target(refs,revision,node,access,supplied=any(n['id']==node['id'] for n in elements(fragment)))
            sr=refs.issue('selection',revision=str(revision.id),target=node['id'],range=capture['range'],
                access=access,content_supplied=True,input=state['jd_turn_id'])
            selection={'selection_ref':sr,'target_ref':target,'content':capture['fragment'][0]['children'],'access':access}
        changes=[]
        if kind in ('current','history'):
            creating=self.service.store.producer(self.scope,revision.id)
            if creating: changes=[self._change(refs,creating)]
        return validate('JdReadSuccess',{'status':'ok','read_kind':kind,'revision_ref':self._revision(refs,revision.id),
            'access':access,'fragment':fragment,'targets':targets,'selection':selection,
            'source_refs':source_refs(fragment),'change_refs':changes,'continuation_ref':continuation})

    def _resolve(self,args,refs):
        bases=set(); commands=[]
        def target(ref,kind='target',expected=None):
            record=refs.require(ref,kind,writable=True)
            if expected and record['element_type']!=expected: raise ValueError('Wrong JD relation endpoint kind')
            bases.add(record['revision'])
            return record
        for original in args['commands']:
            command=deepcopy(original)
            if 'selection_ref' in command:
                r=target(command.pop('selection_ref'),'selection');command.update(target_id=r['target'],range=r['range'])
            else: command['target_id']=target(command.pop('target_ref'))['target']
            if 'destination_ref' in command: command['destination_id']=target(command.pop('destination_ref'))['target']
            if 'set' in command:
                for name in ('knowledge','skill'):
                    key=name+'_refs'
                    if key in command['set']:
                        command['set'][name+'_ids']=[target(ref,expected='jd_'+name)['target'] for ref in command['set'].pop(key)]
            if 'unset' in command: command['unset']=[x.replace('_refs','_ids') if x in ('knowledge_refs','skill_refs') else x for x in command['unset']]
            validate('JdResolvedEditCommand',command); commands.append(command)
        if len(bases)!=1: raise ValueError('All JD references must share one current base')
        return UUID(bases.pop()),commands

    def _change_read(self,args,refs):
        offset=0
        if 'continuation_ref' in args:
            page=refs.require(args['continuation_ref'],'change_page');offset=page['offset'];args=page['args']
        if 'change_ref' in args:
            record=refs.require(args['change_ref'],'change');query=JdChangeQuery(operation_id=UUID(record['operation']))
        else:
            before=refs.require(args['before_revision_ref'],'revision');after=refs.require(args['after_revision_ref'],'revision')
            query=JdChangeQuery(before_id=UUID(before['revision']),after_id=UUID(after['revision']))
        view=self.service.change_read(self.scope,query)
        if view.status!='ok': return read_failure_to_wire(JdReadView(status=view.status))
        before,after=view.before.value,view.after.value
        # Equal endpoint snapshots are exact empty net changes (including a
        # no-change receipt); committed event identity remains separately true.
        if before==after: before,after=[],[]
        end=offset+self.page_size
        continuation=refs.issue('change_page',args=args,offset=end,access='read_only') if end<max(len(before),len(after)) else None
        return validate('JdChangeReadSuccess',{'status':'ok','mode':'change' if view.outcome else 'revision_comparison',
            'change_ref':self._change(refs,view.outcome) if view.outcome else None,
            'origin':view.outcome.origin if view.outcome else None,
            'before_revision_ref':self._revision(refs,view.before.id),'after_revision_ref':self._revision(refs,view.after.id),
            'before_fragment':before[offset:end],'after_fragment':after[offset:end],
            'native_operations':view.outcome.operations if view.outcome else None,
            'source_refs':source_refs([*before[offset:end],*after[offset:end]]),
            'presentation_limitations':['Exact revision fragments; no semantic verification.']+(['More content remains.'] if continuation else []),
            'continuation_ref':continuation})

    def execute(self,name,args,state,call_id):
        refs=IssuedReferences(self.scope,state.get('jd_refs',{}),input_id=state.get('jd_turn_id'))
        binding=state.get('jd_binding')
        if not binding or binding['call']!=call_id or binding['name']!=name or binding['args']!=args or binding['document']!=self.scope.document_id:
            raise ValueError('JD call has no checkpointed factory binding')
        try:
            validate(NAMES[name],args)
            if name=='jd_read':
                envelope={'context':{'document_ref':_ref('document',self.scope),'run_ref':state['jd_turn_id'],
                    'tool_call_id':call_id,'profile':PROFILE},'input':args}
                capture=state.get('jd_selection')
                if capture and capture.get('input')==state['jd_turn_id']:
                    envelope['jd_selection']={'base_revision_ref':revision_ref(self.scope,UUID(capture['revision'])),'range':capture['range']}
                validate('JdReadRuntimeRequest',envelope)
                result=self._read(args,state,refs)
            elif name=='jd_change_read':
                validate('JdChangeReadRuntimeRequest',{'context':{'document_ref':_ref('document',self.scope),
                    'run_ref':state['jd_turn_id'],'tool_call_id':call_id,'profile':PROFILE},'input':args})
                result=self._change_read(args,refs)
            else:
                if 'invalid' in binding: raise ValueError(binding['invalid'])
                base,commands=self._resolve(args,refs)
                digest=request_digest(self.scope,base,commands,'ai')
                if str(base)!=binding['base'] or digest!=binding['digest'] or commands!=binding['commands']:
                    raise ValueError('JD durable operation binding mismatch')
                validate_sources(source_refs(args),state.get('jd_sources',{}),self.source)
                original=self.service.store.revision(self.scope,base)
                validate('JdEditRuntimeRequest',{'context':{'document_ref':_ref('document',self.scope),
                    'run_ref':state['jd_turn_id'],'employee_input_ref':state['jd_turn_id'],
                    'assistant_message_ref':binding['message'],'tool_call_id':call_id,
                    'operation_ref':operation_ref(self.scope,binding['operation']),'request_digest':digest,
                    'base_revision_ref':revision_ref(self.scope,base),'profile':PROFILE,'actor':'ai'},
                    'input':args,'base_value':original.value})
                operation=UUID(binding['operation'])
                outcome=self.service.store.receipt(self.scope,operation,digest)
                if outcome is None:
                    if self.service.store.current(self.scope).id!=base:
                        from analysis_agent.jd_types import JdWriteOutcome
                        outcome=JdWriteOutcome(self.scope,None,base,None,'stale_view','ai',
                            durability='unconfirmed',next_action='reread_current')
                    else:
                        outcome=self.service.edit(JdEditIntent(self.scope,operation,base,digest,commands), cancel=self.cancel, native_calls=self.native_calls)
                result=outcome_to_wire(outcome)
                if outcome.status in ('committed','no_change'): self._change(refs,outcome)
        except (ValueError,SchemaValidationError):
            if name=='jd_edit':
                from analysis_agent.jd_types import JdWriteOutcome
                result=outcome_to_wire(JdWriteOutcome(self.scope,None,None,None,'invalid_input','ai',durability='unconfirmed',next_action='correct_arguments'))
            else: result=read_failure_to_wire(JdReadView(status='invalid_input'))
        message=ToolMessage(json.dumps(result,ensure_ascii=False),name=name,tool_call_id=call_id,id='jd-result:'+call_id)
        results={**state.get('jd_results',{}),message.id:{'name':name,'call':call_id,'revision':result.get('revision_ref',result.get('result_revision_ref')),
            'read_kind':result.get('read_kind'),'continuation':result.get('continuation_ref'),'status':result['status']}}
        pending = result.get('next_action')=='reconcile_operation' or not self.native_calls.quiescent
        return Command(update={'messages':[message],'jd_refs':refs.bindings,'jd_results':results,
            'jd_bindings':{**state.get('jd_bindings',{}),call_id:{**binding,'closed':not pending}},
            'jd_pending_operation':deepcopy(binding) if pending else state.get('jd_pending_operation')})

    def reconcile(self, state, message, call, config):
        """Original saved factory identity only; never execute or replay a tool."""
        from analysis_agent.jd_reconcile import JdAdmittedIdentity, reconcile_identity
        from analysis_agent.publication import PublicationUncertain
        self._scope(config)
        bindings = dict(state.get('jd_bindings',{}))
        binding = bindings.get(call.get('id'))
        if binding is None:
            binding = next((b for b in (state.get('jd_binding'),state.get('jd_pending_operation'))
                            if b and b.get('call')==call.get('id')), None)
        identity = [self.scope.document_id, binding.get('input') if binding else None, message.id, call.get('id')]
        if (not binding or binding.get('document')!=self.scope.document_id
                or binding.get('message')!=message.id or binding.get('name')!=call.get('name')
                or binding.get('args')!=call.get('args')
                or binding.get('operation')!=str(uuid5(NAMESPACE_URL,'jd:'+json.dumps(identity)))
                or not any(isinstance(m,HumanMessage) and m.id==binding['input'] for m in state['messages'])):
            raise PublicationUncertain('JD saved call identity cannot be confirmed')
        if self.stopped_proof is None:
            raise PublicationUncertain('JD stopped-writer evidence is required')
        self.stopped_proof.require(self.scope)
        if call['name']=='jd_edit' and 'invalid' not in binding:
            if request_digest(self.scope,UUID(binding['base']),binding['commands'],'ai')!=binding['digest']:
                raise PublicationUncertain('JD saved request digest differs')
            admitted = JdAdmittedIdentity(self.scope,UUID(binding['operation']),UUID(binding['base']),binding['digest'],'ai')
            result = outcome_to_wire(reconcile_identity(self.service.store,admitted,self.stopped_proof))
            content = json.dumps(result,ensure_ascii=False)
        else:
            content = 'JD result unavailable/discarded: this turn was closed. Do not infer absence of data.'
        paired = any(isinstance(m,ToolMessage) and m.tool_call_id==call['id'] for m in state['messages'])
        bindings[call['id']] = {**binding,'closed':True}
        return Command(update={'jd_bindings':bindings,'jd_pending_operation':None,
            'messages':[] if paired else [ToolMessage(content,name=call['name'],tool_call_id=call['id'],id='jd-result:'+call['id'])]})

    def reconcile_all(self, state, config):
        from analysis_agent.publication import PublicationUncertain
        working = deepcopy(state)
        bindings = dict(working.get('jd_bindings',{}))
        for binding in (working.get('jd_binding'),working.get('jd_pending_operation')):
            if binding and binding['call'] not in bindings:
                bindings[binding['call']] = binding
        working['jd_bindings'] = bindings
        updates = {'messages':[]}
        for binding in tuple(bindings.values()):
            if binding.get('closed'): continue
            message = next((m for m in working['messages'] if isinstance(m,AIMessage) and m.id==binding['message']),None)
            call = next((c for c in message.tool_calls if c.get('id')==binding['call']),None) if message else None
            if call is None: raise PublicationUncertain('JD pending call has no saved response')
            command = self.reconcile(working,message,call,config)
            updates['messages'].extend(command.update['messages'])
            for key,value in command.update.items():
                if key!='messages': updates[key]=value; working[key]=value
            working['messages'].extend(command.update['messages'])
        return updates


class JdExecutionIdentity(AgentMiddleware):
    """Final public model/tool boundary after other wrappers' overrides."""
    def __init__(self,session):
        self.session=session
        self.factories={tool.name:tool for tool in session.tools}

    def wrap_model_call(self,request,handler):
        from analysis_agent.jd_context import _compacted
        prepared=self.session.model_preparation.get()
        if prepared is None: raise ValueError('JD model request lacks preparation')
        schemas,notice,manifest,basis,refs,projection=prepared
        actual=[]
        for item in request.tools:
            name=item.name if hasattr(item,'name') else item.get('name',item.get('function',{}).get('name'))
            if name in NAMES: actual.append(item)
        if (actual!=schemas or not request.messages or request.messages[-1].model_dump()!=notice
                or [m.id for m in request.messages[:-1] if isinstance(m,ToolMessage)
                    and m.id in request.state.get('jd_results',{})][-15:]!=manifest['visible_jd_results']
                or _jd_message_projection(request.messages[:-1],manifest['visible_jd_results'])!=projection
                or _compacted(request.messages)!=manifest['context_cut']):
            raise ValueError('JD model request changed after preparation')
        return self.session.confirm_model_response(handler(request),manifest,basis,refs)

    def wrap_tool_call(self,request,handler):
        call=request.tool_call
        binding=request.state.get('jd_binding')
        bound=binding and binding.get('call')==call.get('id') and binding.get('name') in NAMES
        if call['name'] in NAMES or bound:
            name=binding['name'] if bound else call['name']
            if (not bound or call['name']!=name or call.get('args')!=binding['args']
                    or request.tool is not self.factories.get(name)):
                raise ValueError('JD execution requires the exact checkpointed factory call')
        return handler(request)
