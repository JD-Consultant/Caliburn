"""Find controlled addresses without treating Markdown markup as a filename.

CommonMark owns presentation parsing. Existence/scope belong to the actual
artifact and conversation readers, not this parser or the language model.
"""
import re

from markdown_it import MarkdownIt
from linkify_it import LinkifyIt


PREFIXES = ('/interviews/', '/memory/', 'conversation:')
_LITERAL = re.compile(r'''(?<![A-Za-z0-9_/:?=&%#@.+~-])(?:/interviews/|/memory/|conversation:)[^\s<>()（）\[\]`"'，。；！？：、]*''')
_CODE_LITERAL = re.compile(r'''(?<![A-Za-z0-9_/:?=&%#@.+~-])(?:/interviews/|/memory/|conversation:)[^\s<>()\[\]`"']*''')


def controlled_references(text: str) -> set[str]:
    # A local parser/env per call: no shared mutable reference-definition state.
    env = {}
    tokens = MarkdownIt('commonmark', {'html': False}).parse(text, env)
    linkifier = LinkifyIt(options={'fuzzy_link': False, 'fuzzy_email': False})
    references = set()
    while tokens:
        token = tokens.pop()
        tokens.extend(token.children or ())
        for attribute in ('href', 'src'):
            target = token.attrGet(attribute)
            if target and target.startswith(PREFIXES):
                # Explicit destinations are exact. Never trim a malformed href
                # into some different but readable source.
                references.add(target)
        if token.type in {'text', 'code_inline', 'code_block', 'fence'}:
            # Official link recognizer provides full URI spans. A local-looking
            # suffix inside an external URI is not a separate Memory address.
            external = linkifier.match(token.content) or ()
            pattern = _LITERAL if token.type == 'text' else _CODE_LITERAL
            for match in pattern.finditer(token.content):
                if any(link.index <= match.start() < link.last_index for link in external):
                    continue
                # Punctuation outside a bare prose address is presentation;
                # inside a code literal it is part of the exact supplied value.
                references.add(match.group().rstrip('.,;!') if token.type == 'text' else match.group())
    definitions = [*env.get('references', {}).values(), *env.get('duplicate_refs', ())]
    for definition in definitions:
        if definition['href'].startswith(PREFIXES):
            references.add(definition['href'])
    return references
