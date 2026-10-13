/* Generated from FastAPI OpenAPI; do not edit. */
//#region \0rolldown/runtime.js
var e = (e, t) => () => (t || (e((t = { exports: {} }).exports, t), (e = null)), t.exports),
  t = /* @__PURE__ */ e((e) => {
    Object.defineProperty(e, '__esModule', { value: !0 });
    function t(e) {
      let t = e.length,
        n = 0,
        r = 0,
        i;
      for (; r < t;)
        (n++,
          (i = e.charCodeAt(r++)),
          i >= 55296 &&
            i <= 56319 &&
            r < t &&
            ((i = e.charCodeAt(r)), (i & 64512) == 56320 && r++));
      return n;
    }
    ((e.default = t), (t.code = 'require("ajv/dist/runtime/ucs2length").default'));
  }),
  n = /* @__PURE__ */ e((e, t) => {
    t.exports = function e(t, n) {
      if (t === n) return !0;
      if (t && n && typeof t == 'object' && typeof n == 'object') {
        if (t.constructor !== n.constructor) return !1;
        var r, i, a;
        if (Array.isArray(t)) {
          if (((r = t.length), r != n.length)) return !1;
          for (i = r; i-- !== 0;) if (!e(t[i], n[i])) return !1;
          return !0;
        }
        if (t.constructor === RegExp) return t.source === n.source && t.flags === n.flags;
        if (t.valueOf !== Object.prototype.valueOf) return t.valueOf() === n.valueOf();
        if (t.toString !== Object.prototype.toString) return t.toString() === n.toString();
        if (((a = Object.keys(t)), (r = a.length), r !== Object.keys(n).length)) return !1;
        for (i = r; i-- !== 0;) if (!Object.prototype.hasOwnProperty.call(n, a[i])) return !1;
        for (i = r; i-- !== 0;) {
          var o = a[i];
          if (!e(t[o], n[o])) return !1;
        }
        return !0;
      }
      return t !== t && n !== n;
    };
  }),
  r = /* @__PURE__ */ e((e) => {
    Object.defineProperty(e, '__esModule', { value: !0 });
    var t = n();
    ((t.code = 'require("ajv/dist/runtime/equal").default'), (e.default = t));
  }),
  i = /* @__PURE__ */ e((e) => {
    (Object.defineProperty(e, '__esModule', { value: !0 }),
      (e.formatNames = e.fastFormats = e.fullFormats = void 0));
    function t(e, t) {
      return {
        validate: e,
        compare: t,
      };
    }
    ((e.fullFormats = {
      date: t(a, o),
      time: t(c(!0), l),
      'date-time': t(f(!0), p),
      'iso-time': t(c(), u),
      'iso-date-time': t(f(), m),
      duration: /^P(?!$)((\d+Y)?(\d+M)?(\d+D)?(T(?=\d)(\d+H)?(\d+M)?(\d+S)?)?|(\d+W)?)$/,
      uri: ee,
      'uri-reference':
        /^(?:[a-z][a-z0-9+\-.]*:)?(?:\/?\/(?:(?:[a-z0-9\-._~!$&'()*+,;=:]|%[0-9a-f]{2})*@)?(?:\[(?:(?:(?:(?:[0-9a-f]{1,4}:){6}|::(?:[0-9a-f]{1,4}:){5}|(?:[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){4}|(?:(?:[0-9a-f]{1,4}:){0,1}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){3}|(?:(?:[0-9a-f]{1,4}:){0,2}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){2}|(?:(?:[0-9a-f]{1,4}:){0,3}[0-9a-f]{1,4})?::[0-9a-f]{1,4}:|(?:(?:[0-9a-f]{1,4}:){0,4}[0-9a-f]{1,4})?::)(?:[0-9a-f]{1,4}:[0-9a-f]{1,4}|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|(?:(?:[0-9a-f]{1,4}:){0,5}[0-9a-f]{1,4})?::[0-9a-f]{1,4}|(?:(?:[0-9a-f]{1,4}:){0,6}[0-9a-f]{1,4})?::)|[Vv][0-9a-f]+\.[a-z0-9\-._~!$&'()*+,;=:]+)\]|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)|(?:[a-z0-9\-._~!$&'"()*+,;=]|%[0-9a-f]{2})*)(?::\d*)?(?:\/(?:[a-z0-9\-._~!$&'"()*+,;=:@]|%[0-9a-f]{2})*)*|\/(?:(?:[a-z0-9\-._~!$&'"()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'"()*+,;=:@]|%[0-9a-f]{2})*)*)?|(?:[a-z0-9\-._~!$&'"()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'"()*+,;=:@]|%[0-9a-f]{2})*)*)?(?:\?(?:[a-z0-9\-._~!$&'"()*+,;=:@/?]|%[0-9a-f]{2})*)?(?:#(?:[a-z0-9\-._~!$&'"()*+,;=:@/?]|%[0-9a-f]{2})*)?$/i,
      'uri-template':
        /^(?:(?:[^\x00-\x20"'<>%\\^`{|}]|%[0-9a-f]{2})|\{[+#./;?&=,!@|]?(?:[a-z0-9_]|%[0-9a-f]{2})+(?::[1-9][0-9]{0,3}|\*)?(?:,(?:[a-z0-9_]|%[0-9a-f]{2})+(?::[1-9][0-9]{0,3}|\*)?)*\})*$/i,
      url: /^(?:https?|ftp):\/\/(?:\S+(?::\S*)?@)?(?:(?!(?:10|127)(?:\.\d{1,3}){3})(?!(?:169\.254|192\.168)(?:\.\d{1,3}){2})(?!172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?:[1-9]\d?|1\d\d|2[01]\d|22[0-3])(?:\.(?:1?\d{1,2}|2[0-4]\d|25[0-5])){2}(?:\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-4]))|(?:(?:[a-z0-9\u{00a1}-\u{ffff}]+-)*[a-z0-9\u{00a1}-\u{ffff}]+)(?:\.(?:[a-z0-9\u{00a1}-\u{ffff}]+-)*[a-z0-9\u{00a1}-\u{ffff}]+)*(?:\.(?:[a-z\u{00a1}-\u{ffff}]{2,})))(?::\d{2,5})?(?:\/[^\s]*)?$/iu,
      email:
        /^[a-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+/=?^_`{|}~-]+)*@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/i,
      hostname:
        /^(?=.{1,253}\.?$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[-0-9a-z]{0,61}[0-9a-z])?)*\.?$/i,
      ipv4: /^(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)$/,
      ipv6: /^((([0-9a-f]{1,4}:){7}([0-9a-f]{1,4}|:))|(([0-9a-f]{1,4}:){6}(:[0-9a-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9a-f]{1,4}:){5}(((:[0-9a-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9a-f]{1,4}:){4}(((:[0-9a-f]{1,4}){1,3})|((:[0-9a-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9a-f]{1,4}:){3}(((:[0-9a-f]{1,4}){1,4})|((:[0-9a-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9a-f]{1,4}:){2}(((:[0-9a-f]{1,4}){1,5})|((:[0-9a-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9a-f]{1,4}:){1}(((:[0-9a-f]{1,4}){1,6})|((:[0-9a-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9a-f]{1,4}){1,7})|((:[0-9a-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))$/i,
      regex: S,
      uuid: /^(?:urn:uuid:)?[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i,
      'json-pointer': /^(?:\/(?:[^~/]|~0|~1)*)*$/,
      'json-pointer-uri-fragment': /^#(?:\/(?:[a-z0-9_\-.!$&'()*+,;:=@]|%[0-9a-f]{2}|~0|~1)*)*$/i,
      'relative-json-pointer': /^(?:0|[1-9][0-9]*)(?:#|(?:\/(?:[^~/]|~0|~1)*)*)$/,
      byte: _,
      int32: {
        type: 'number',
        validate: y,
      },
      int64: {
        type: 'number',
        validate: b,
      },
      float: {
        type: 'number',
        validate: x,
      },
      double: {
        type: 'number',
        validate: x,
      },
      password: !0,
      binary: !0,
    }),
      (e.fastFormats = {
        ...e.fullFormats,
        date: t(/^\d\d\d\d-[0-1]\d-[0-3]\d$/, o),
        time: t(/^(?:[0-2]\d:[0-5]\d:[0-5]\d|23:59:60)(?:\.\d+)?(?:z|[+-]\d\d(?::?\d\d)?)$/i, l),
        'date-time': t(
          /^\d\d\d\d-[0-1]\d-[0-3]\dt(?:[0-2]\d:[0-5]\d:[0-5]\d|23:59:60)(?:\.\d+)?(?:z|[+-]\d\d(?::?\d\d)?)$/i,
          p,
        ),
        'iso-time': t(
          /^(?:[0-2]\d:[0-5]\d:[0-5]\d|23:59:60)(?:\.\d+)?(?:z|[+-]\d\d(?::?\d\d)?)?$/i,
          u,
        ),
        'iso-date-time': t(
          /^\d\d\d\d-[0-1]\d-[0-3]\d[t\s](?:[0-2]\d:[0-5]\d:[0-5]\d|23:59:60)(?:\.\d+)?(?:z|[+-]\d\d(?::?\d\d)?)?$/i,
          m,
        ),
        uri: /^(?:[a-z][a-z0-9+\-.]*:)(?:\/?\/)?[^\s]*$/i,
        'uri-reference': /^(?:(?:[a-z][a-z0-9+\-.]*:)?\/?\/)?(?:[^\\\s#][^\s#]*)?(?:#[^\\\s]*)?$/i,
        email:
          /^[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$/i,
      }),
      (e.formatNames = Object.keys(e.fullFormats)));
    function n(e) {
      return e % 4 == 0 && (e % 100 != 0 || e % 400 == 0);
    }
    var r = /^(\d\d\d\d)-(\d\d)-(\d\d)$/,
      i = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    function a(e) {
      let t = r.exec(e);
      if (!t) return !1;
      let a = +t[1],
        o = +t[2],
        s = +t[3];
      return o >= 1 && o <= 12 && s >= 1 && s <= (o === 2 && n(a) ? 29 : i[o]);
    }
    function o(e, t) {
      if (e && t) return e > t ? 1 : e < t ? -1 : 0;
    }
    var s = /^(\d\d):(\d\d):(\d\d(?:\.\d+)?)(z|([+-])(\d\d)(?::?(\d\d))?)?$/i;
    function c(e) {
      return function (t) {
        let n = s.exec(t);
        if (!n) return !1;
        let r = +n[1],
          i = +n[2],
          a = +n[3],
          o = n[4],
          c = n[5] === '-' ? -1 : 1,
          l = +(n[6] || 0),
          u = +(n[7] || 0);
        if (l > 23 || u > 59 || (e && !o)) return !1;
        if (r <= 23 && i <= 59 && a < 60) return !0;
        let d = i - u * c,
          f = r - l * c - +(d < 0);
        return (f === 23 || f === -1) && (d === 59 || d === -1) && a < 61;
      };
    }
    function l(e, t) {
      if (!(e && t)) return;
      let n = /* @__PURE__ */ new Date('2020-01-01T' + e).valueOf(),
        r = /* @__PURE__ */ new Date('2020-01-01T' + t).valueOf();
      if (n && r) return n - r;
    }
    function u(e, t) {
      if (!(e && t)) return;
      let n = s.exec(e),
        r = s.exec(t);
      if (n && r)
        return ((e = n[1] + n[2] + n[3]), (t = r[1] + r[2] + r[3]), e > t ? 1 : e < t ? -1 : 0);
    }
    var d = /t|\s/i;
    function f(e) {
      let t = c(e);
      return function (e) {
        let n = e.split(d);
        return n.length === 2 && a(n[0]) && t(n[1]);
      };
    }
    function p(e, t) {
      if (!(e && t)) return;
      let n = new Date(e).valueOf(),
        r = new Date(t).valueOf();
      if (n && r) return n - r;
    }
    function m(e, t) {
      if (!(e && t)) return;
      let [n, r] = e.split(d),
        [i, a] = t.split(d),
        s = o(n, i);
      if (s !== void 0) return s || l(r, a);
    }
    var h = /\/|:/,
      g =
        /^(?:[a-z][a-z0-9+\-.]*:)(?:\/?\/(?:(?:[a-z0-9\-._~!$&'()*+,;=:]|%[0-9a-f]{2})*@)?(?:\[(?:(?:(?:(?:[0-9a-f]{1,4}:){6}|::(?:[0-9a-f]{1,4}:){5}|(?:[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){4}|(?:(?:[0-9a-f]{1,4}:){0,1}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){3}|(?:(?:[0-9a-f]{1,4}:){0,2}[0-9a-f]{1,4})?::(?:[0-9a-f]{1,4}:){2}|(?:(?:[0-9a-f]{1,4}:){0,3}[0-9a-f]{1,4})?::[0-9a-f]{1,4}:|(?:(?:[0-9a-f]{1,4}:){0,4}[0-9a-f]{1,4})?::)(?:[0-9a-f]{1,4}:[0-9a-f]{1,4}|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?))|(?:(?:[0-9a-f]{1,4}:){0,5}[0-9a-f]{1,4})?::[0-9a-f]{1,4}|(?:(?:[0-9a-f]{1,4}:){0,6}[0-9a-f]{1,4})?::)|[Vv][0-9a-f]+\.[a-z0-9\-._~!$&'()*+,;=:]+)\]|(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)|(?:[a-z0-9\-._~!$&'()*+,;=]|%[0-9a-f]{2})*)(?::\d*)?(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*|\/(?:(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*)?|(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})+(?:\/(?:[a-z0-9\-._~!$&'()*+,;=:@]|%[0-9a-f]{2})*)*)(?:\?(?:[a-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9a-f]{2})*)?(?:#(?:[a-z0-9\-._~!$&'()*+,;=:@/?]|%[0-9a-f]{2})*)?$/i;
    function ee(e) {
      return h.test(e) && g.test(e);
    }
    var te = /^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/gm;
    function _(e) {
      return ((te.lastIndex = 0), te.test(e));
    }
    var ne = -(2 ** 31),
      v = 2 ** 31 - 1;
    function y(e) {
      return Number.isInteger(e) && e <= v && e >= ne;
    }
    function b(e) {
      return Number.isInteger(e);
    }
    function x() {
      return !0;
    }
    var re = /[^\\]\\Z/;
    function S(e) {
      if (re.test(e)) return !1;
      try {
        return (new RegExp(e), !0);
      } catch {
        return !1;
      }
    }
  }),
  a = /* @__PURE__ */ e((e) => {
    e.isAcceptedInterviewInput = c;
    var n = /^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/i,
      a = t().default,
      o = /* @__PURE__ */ RegExp(
        '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
        'u',
      );
    function s(
      e,
      {
        instancePath: t = '',
        parentData: r,
        parentDataProperty: i,
        rootData: c = e,
        dynamicAnchors: l = {},
      } = {},
    ) {
      let u = s.evaluated;
      if (
        (u.dynamicProps && (u.props = void 0),
        u.dynamicItems && (u.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) > 36)
          return (
            (s.errors = [
              {
                instancePath: t,
                schemaPath: '#/maxLength',
                keyword: 'maxLength',
                params: { limit: 36 },
                message: 'must NOT have more than 36 characters',
              },
            ]),
            !1
          );
        if (a(e) < 36)
          return (
            (s.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 36 },
                message: 'must NOT have fewer than 36 characters',
              },
            ]),
            !1
          );
        if (!o.test(e))
          return (
            (s.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
                },
                message:
                  'must match pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"',
              },
            ]),
            !1
          );
        if (!n.test(e))
          return (
            (s.errors = [
              {
                instancePath: t,
                schemaPath: '#/format',
                keyword: 'format',
                params: { format: 'uuid' },
                message: 'must match format "uuid"',
              },
            ]),
            !1
          );
      } else
        return (
          (s.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((s.errors = null), !0);
    }
    s.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function c(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        l = 0,
        u = c.evaluated;
      if ((u.dynamicProps && (u.props = void 0), u.dynamicItems && (u.items = void 0), l === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_file_id === void 0 && (n = 'job_file_id')) ||
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.source_id === void 0 && (n = 'source_id')) ||
            (e.execution_id === void 0 && (n = 'execution_id'))
          )
            return (
              (c.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = l;
            for (let n in e)
              if (
                n !== 'job_file_id' &&
                n !== 'command_id' &&
                n !== 'source_id' &&
                n !== 'execution_id'
              )
                return (
                  (c.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === l) {
              if (e.job_file_id !== void 0) {
                let n = l;
                s(e.job_file_id, {
                  instancePath: t + '/job_file_id',
                  parentData: e,
                  parentDataProperty: 'job_file_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (l = o.length));
                var d = n === l;
              } else var d = !0;
              if (d) {
                if (e.command_id !== void 0) {
                  let n = l;
                  s(e.command_id, {
                    instancePath: t + '/command_id',
                    parentData: e,
                    parentDataProperty: 'command_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (l = o.length));
                  var d = n === l;
                } else var d = !0;
                if (d) {
                  if (e.source_id !== void 0) {
                    let n = l;
                    s(e.source_id, {
                      instancePath: t + '/source_id',
                      parentData: e,
                      parentDataProperty: 'source_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (l = o.length));
                    var d = n === l;
                  } else var d = !0;
                  if (d) {
                    if (e.execution_id !== void 0) {
                      let n = l;
                      s(e.execution_id, {
                        instancePath: t + '/execution_id',
                        parentData: e,
                        parentDataProperty: 'execution_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (l = o.length));
                      var d = n === l;
                    } else var d = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (c.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((c.errors = o), l === 0);
    }
    ((c.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isAddDetail = p));
    var l = {
      type: 'string',
      enum: ['outcome', 'requirement'],
      title: 'DetailKind',
    };
    function u(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = u.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'outcome' && e !== 'requirement'
            ? ((u.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: l.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((u.errors = null), !0)
          : ((u.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    u.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    var d = /* @__PURE__ */ RegExp(
      '^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$',
      'u',
    );
    function f(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = f.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) < 1)
          return (
            (f.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
        if (!d.test(e))
          return (
            (f.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$',
                },
                message:
                  'must match pattern "^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$"',
              },
            ]),
            !1
          );
      } else
        return (
          (f.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((f.errors = null), !0);
    }
    f.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function p(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = p.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (p.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'kind' && n !== 'text')
                return (
                  (p.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (p.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'add_detail')
                  return (
                    (p.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'add_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.kind !== void 0) {
                  let n = s;
                  u(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? u.errors : o.concat(u.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.text !== void 0) {
                    let n = s;
                    f(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (p.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((p.errors = o), s === 0);
    }
    ((p.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isAllowedControl = h));
    var m = {
      type: 'string',
      enum: ['pause', 'cancel', 'resume'],
    };
    function h(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = h.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'pause' && e !== 'cancel' && e !== 'resume'
            ? ((h.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: m.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((h.errors = null), !0)
          : ((h.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((h.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isArea = g));
    function g(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = g.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.scope_text === void 0 && (n = 'scope_text'))
          )
            return (
              (g.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'area_id' && n !== 'title' && n !== 'scope_text')
                return (
                  (g.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.area_id !== void 0) {
                let n = c;
                s(e.area_id, {
                  instancePath: t + '/area_id',
                  parentData: e,
                  parentDataProperty: 'area_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.title !== void 0) {
                  let n = e.title,
                    r = c,
                    i = c,
                    a = !1,
                    s = c;
                  if (typeof n != 'string') {
                    let e = {
                      instancePath: t + '/title',
                      schemaPath: '#/properties/title/anyOf/0/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = s === c;
                  a ||= d;
                  let l = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/title',
                      schemaPath: '#/properties/title/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = l === c;
                  if (((a ||= d), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/title',
                      schemaPath: '#/properties/title/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (g.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.scope_text !== void 0) {
                    let n = e.scope_text,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = s === c;
                    a ||= f;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = l === c;
                    if (((a ||= f), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (g.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (g.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((g.errors = o), c === 0);
    }
    ((g.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isAreaField = te));
    var ee = {
      type: 'string',
      enum: ['title', 'scope_text'],
      title: 'AreaField',
    };
    function te(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = te.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'title' && e !== 'scope_text'
            ? ((te.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: ee.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((te.errors = null), !0)
          : ((te.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((te.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isAreaFieldChange = _));
    function _(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = _.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (_.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (_.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = s;
                te(e.field, {
                  instancePath: t + '/field',
                  parentData: e,
                  parentDataProperty: 'field',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? te.errors : o.concat(te.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = e.value,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (_.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (_.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((_.errors = o), s === 0);
    }
    ((_.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCall = v));
    var ne = {
      properties: {
        request_id: { $ref: '#/components/schemas/WireUuid' },
        response_id: {
          type: 'string',
          title: 'Response Id',
        },
        call_id: {
          type: 'string',
          title: 'Call Id',
        },
        name: {
          type: 'string',
          title: 'Name',
        },
        arguments: {
          type: 'string',
          title: 'Arguments',
        },
        result_state: {
          type: 'string',
          enum: ['recorded', 'not_recorded'],
          title: 'Result State',
        },
        output: {
          anyOf: [{ type: 'string' }, { type: 'null' }],
          title: 'Output',
        },
      },
      additionalProperties: !1,
      type: 'object',
      required: [
        'request_id',
        'response_id',
        'call_id',
        'name',
        'arguments',
        'result_state',
        'output',
      ],
      title: 'Call',
    };
    function v(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = v.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.request_id === void 0 && (n = 'request_id')) ||
            (e.response_id === void 0 && (n = 'response_id')) ||
            (e.call_id === void 0 && (n = 'call_id')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.arguments === void 0 && (n = 'arguments')) ||
            (e.result_state === void 0 && (n = 'result_state')) ||
            (e.output === void 0 && (n = 'output'))
          )
            return (
              (v.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'request_id' &&
                n !== 'response_id' &&
                n !== 'call_id' &&
                n !== 'name' &&
                n !== 'arguments' &&
                n !== 'result_state' &&
                n !== 'output'
              )
                return (
                  (v.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.request_id !== void 0) {
                let n = c;
                s(e.request_id, {
                  instancePath: t + '/request_id',
                  parentData: e,
                  parentDataProperty: 'request_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.response_id !== void 0) {
                  let n = c;
                  if (typeof e.response_id != 'string')
                    return (
                      (v.errors = [
                        {
                          instancePath: t + '/response_id',
                          schemaPath: '#/properties/response_id/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.call_id !== void 0) {
                    let n = c;
                    if (typeof e.call_id != 'string')
                      return (
                        (v.errors = [
                          {
                            instancePath: t + '/call_id',
                            schemaPath: '#/properties/call_id/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.name !== void 0) {
                      let n = c;
                      if (typeof e.name != 'string')
                        return (
                          (v.errors = [
                            {
                              instancePath: t + '/name',
                              schemaPath: '#/properties/name/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.arguments !== void 0) {
                        let n = c;
                        if (typeof e.arguments != 'string')
                          return (
                            (v.errors = [
                              {
                                instancePath: t + '/arguments',
                                schemaPath: '#/properties/arguments/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              },
                            ]),
                            !1
                          );
                        var u = n === c;
                      } else var u = !0;
                      if (u) {
                        if (e.result_state !== void 0) {
                          let n = e.result_state,
                            r = c;
                          if (typeof n != 'string')
                            return (
                              (v.errors = [
                                {
                                  instancePath: t + '/result_state',
                                  schemaPath: '#/properties/result_state/type',
                                  keyword: 'type',
                                  params: { type: 'string' },
                                  message: 'must be string',
                                },
                              ]),
                              !1
                            );
                          if (n !== 'recorded' && n !== 'not_recorded')
                            return (
                              (v.errors = [
                                {
                                  instancePath: t + '/result_state',
                                  schemaPath: '#/properties/result_state/enum',
                                  keyword: 'enum',
                                  params: { allowedValues: ne.properties.result_state.enum },
                                  message: 'must be equal to one of the allowed values',
                                },
                              ]),
                              !1
                            );
                          var u = r === c;
                        } else var u = !0;
                        if (u) {
                          if (e.output !== void 0) {
                            let n = e.output,
                              r = c,
                              i = c,
                              a = !1,
                              s = c;
                            if (typeof n != 'string') {
                              let e = {
                                instancePath: t + '/output',
                                schemaPath: '#/properties/output/anyOf/0/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              };
                              (o === null ? (o = [e]) : o.push(e), c++);
                            }
                            var d = s === c;
                            a ||= d;
                            let l = c;
                            if (n !== null) {
                              let e = {
                                instancePath: t + '/output',
                                schemaPath: '#/properties/output/anyOf/1/type',
                                keyword: 'type',
                                params: { type: 'null' },
                                message: 'must be null',
                              };
                              (o === null ? (o = [e]) : o.push(e), c++);
                            }
                            var d = l === c;
                            if (((a ||= d), a))
                              ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                            else {
                              let e = {
                                instancePath: t + '/output',
                                schemaPath: '#/properties/output/anyOf',
                                keyword: 'anyOf',
                                params: {},
                                message: 'must match a schema in anyOf',
                              };
                              return (o === null ? (o = [e]) : o.push(e), c++, (v.errors = o), !1);
                            }
                            var u = r === c;
                          } else var u = !0;
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (v.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((v.errors = o), c === 0);
    }
    ((v.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCandidateJdPreview = ae));
    function y(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = y.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_title === void 0 && (n = 'job_title')) ||
            (e.organization_unit === void 0 && (n = 'organization_unit')) ||
            (e.reports_to === void 0 && (n = 'reports_to')) ||
            (e.purpose === void 0 && (n = 'purpose'))
          )
            return (
              (y.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'job_title' &&
                n !== 'organization_unit' &&
                n !== 'reports_to' &&
                n !== 'purpose'
              )
                return (
                  (y.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.job_title !== void 0) {
                let n = e.job_title,
                  r = s,
                  i = s,
                  a = !1,
                  c = s;
                if (typeof n != 'string') {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf/0/type',
                    keyword: 'type',
                    params: { type: 'string' },
                    message: 'must be string',
                  };
                  (o === null ? (o = [e]) : o.push(e), s++);
                }
                var l = c === s;
                a ||= l;
                let d = s;
                if (n !== null) {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf/1/type',
                    keyword: 'type',
                    params: { type: 'null' },
                    message: 'must be null',
                  };
                  (o === null ? (o = [e]) : o.push(e), s++);
                }
                var l = d === s;
                if (((a ||= l), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                else {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf',
                    keyword: 'anyOf',
                    params: {},
                    message: 'must match a schema in anyOf',
                  };
                  return (o === null ? (o = [e]) : o.push(e), s++, (y.errors = o), !1);
                }
                var u = r === s;
              } else var u = !0;
              if (u) {
                if (e.organization_unit !== void 0) {
                  let n = e.organization_unit,
                    r = s,
                    i = s,
                    a = !1,
                    c = s;
                  if (typeof n != 'string') {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf/0/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var d = c === s;
                  a ||= d;
                  let l = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var d = l === s;
                  if (((a ||= d), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (y.errors = o), !1);
                  }
                  var u = r === s;
                } else var u = !0;
                if (u) {
                  if (e.reports_to !== void 0) {
                    let n = e.reports_to,
                      r = s,
                      i = s,
                      a = !1,
                      c = s;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var f = c === s;
                    a ||= f;
                    let l = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var f = l === s;
                    if (((a ||= f), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (y.errors = o), !1);
                    }
                    var u = r === s;
                  } else var u = !0;
                  if (u) {
                    if (e.purpose !== void 0) {
                      let n = e.purpose,
                        r = s,
                        i = s,
                        a = !1,
                        c = s;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), s++);
                      }
                      var p = c === s;
                      a ||= p;
                      let l = s;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), s++);
                      }
                      var p = l === s;
                      if (((a ||= p), a))
                        ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), s++, (y.errors = o), !1);
                      }
                      var u = r === s;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (y.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((y.errors = o), s === 0);
    }
    y.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function b(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = b.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.detail_id === void 0 && (n = 'detail_id')) || (e.text === void 0 && (n = 'text')))
            return (
              (b.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'detail_id' && n !== 'text')
                return (
                  (b.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.detail_id !== void 0) {
                let n = c;
                s(e.detail_id, {
                  instancePath: t + '/detail_id',
                  parentData: e,
                  parentDataProperty: 'detail_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.text !== void 0) {
                  let n = c;
                  if (typeof e.text != 'string')
                    return (
                      (b.errors = [
                        {
                          instancePath: t + '/text',
                          schemaPath: '#/properties/text/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (b.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((b.errors = o), c === 0);
    }
    b.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function x(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = x.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.outcomes === void 0 && (n = 'outcomes')) ||
            (e.requirements === void 0 && (n = 'requirements'))
          )
            return (
              (x.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'task_id' &&
                n !== 'area_id' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'outcomes' &&
                n !== 'requirements'
              )
                return (
                  (x.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.task_id !== void 0) {
                let n = c;
                s(e.task_id, {
                  instancePath: t + '/task_id',
                  parentData: e,
                  parentDataProperty: 'task_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = e.area_id,
                    r = c,
                    l = c,
                    f = !1,
                    p = c;
                  s(n, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = p === c;
                  f ||= d;
                  let m = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = m === c;
                  if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (x.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.title !== void 0) {
                    let n = e.title,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = s === c;
                    a ||= f;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = l === c;
                    if (((a ||= f), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (x.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = c,
                        i = c,
                        a = !1,
                        s = c;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var p = s === c;
                      a ||= p;
                      let l = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var p = l === c;
                      if (((a ||= p), a))
                        ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (x.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.outcomes !== void 0) {
                        let n = e.outcomes,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (b(n[r], {
                                  instancePath: t + '/outcomes/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? b.errors : o.concat(b.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (x.errors = [
                                {
                                  instancePath: t + '/outcomes',
                                  schemaPath: '#/properties/outcomes/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.requirements !== void 0) {
                          let n = e.requirements,
                            r = c;
                          if (c === r) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (b(n[r], {
                                    instancePath: t + '/requirements/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? b.errors : o.concat(b.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else
                              return (
                                (x.errors = [
                                  {
                                    instancePath: t + '/requirements',
                                    schemaPath: '#/properties/requirements/type',
                                    keyword: 'type',
                                    params: { type: 'array' },
                                    message: 'must be array',
                                  },
                                ]),
                                !1
                              );
                          }
                          var u = r === c;
                        } else var u = !0;
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (x.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((x.errors = o), c === 0);
    }
    x.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    var re = {
      type: 'string',
      enum: ['knowledge', 'skill'],
      title: 'CapabilityKind',
    };
    function S(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = S.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'knowledge' && e !== 'skill'
            ? ((S.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: re.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((S.errors = null), !0)
          : ((S.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    S.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function C(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = C.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.description === void 0 && (n = 'description'))
          )
            return (
              (C.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'capability_id' && n !== 'kind' && n !== 'name' && n !== 'description')
                return (
                  (C.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.capability_id !== void 0) {
                let n = c;
                s(e.capability_id, {
                  instancePath: t + '/capability_id',
                  parentData: e,
                  parentDataProperty: 'capability_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.kind !== void 0) {
                  let n = c;
                  S(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? S.errors : o.concat(S.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.name !== void 0) {
                    let n = e.name,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = s === c;
                    a ||= d;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = l === c;
                    if (((a ||= d), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (C.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = c,
                        i = c,
                        a = !1,
                        s = c;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = s === c;
                      a ||= f;
                      let l = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = l === c;
                      if (((a ||= f), a))
                        ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (C.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (C.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((C.errors = o), c === 0);
    }
    C.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function w(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = w.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id'))
          )
            return (
              (w.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'task_id' && n !== 'capability_id')
                return (
                  (w.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.task_id !== void 0) {
                let n = c;
                s(e.task_id, {
                  instancePath: t + '/task_id',
                  parentData: e,
                  parentDataProperty: 'task_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (w.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((w.errors = o), c === 0);
    }
    w.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function T(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = T.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.scope_text === void 0 && (n = 'scope_text'))
          )
            return (
              (T.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'collaborator_id' && n !== 'name' && n !== 'scope_text')
                return (
                  (T.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.collaborator_id !== void 0) {
                let n = c;
                s(e.collaborator_id, {
                  instancePath: t + '/collaborator_id',
                  parentData: e,
                  parentDataProperty: 'collaborator_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.name !== void 0) {
                  let n = e.name,
                    r = c,
                    i = c,
                    a = !1,
                    s = c;
                  if (typeof n != 'string') {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf/0/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = s === c;
                  a ||= d;
                  let l = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = l === c;
                  if (((a ||= d), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (T.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.scope_text !== void 0) {
                    let n = e.scope_text,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = s === c;
                    a ||= f;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = l === c;
                    if (((a ||= f), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (T.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (T.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((T.errors = o), c === 0);
    }
    T.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    var ie = {
      type: 'string',
      enum: [
        'work_environment',
        'schedule_travel',
        'shared_authority',
        'shared_collaboration',
        'qualification',
      ],
      title: 'ConditionKind',
    };
    function E(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = E.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'work_environment' &&
            e !== 'schedule_travel' &&
            e !== 'shared_authority' &&
            e !== 'shared_collaboration' &&
            e !== 'qualification'
            ? ((E.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: ie.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((E.errors = null), !0)
          : ((E.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    E.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function D(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = D.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (D.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'condition_id' && n !== 'kind' && n !== 'text')
                return (
                  (D.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.condition_id !== void 0) {
                let n = c;
                s(e.condition_id, {
                  instancePath: t + '/condition_id',
                  parentData: e,
                  parentDataProperty: 'condition_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.kind !== void 0) {
                  let n = c;
                  E(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? E.errors : o.concat(E.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.text !== void 0) {
                    let n = c;
                    if (typeof e.text != 'string')
                      return (
                        (D.errors = [
                          {
                            instancePath: t + '/text',
                            schemaPath: '#/properties/text/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (D.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((D.errors = o), c === 0);
    }
    D.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function O(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = O.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.areas === void 0 && (n = 'areas')) ||
            (e.tasks === void 0 && (n = 'tasks')) ||
            (e.capabilities === void 0 && (n = 'capabilities')) ||
            (e.task_links === void 0 && (n = 'task_links')) ||
            (e.collaborators === void 0 && (n = 'collaborators')) ||
            (e.conditions === void 0 && (n = 'conditions'))
          )
            return (
              (O.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'revision_id' &&
                n !== 'areas' &&
                n !== 'tasks' &&
                n !== 'capabilities' &&
                n !== 'task_links' &&
                n !== 'collaborators' &&
                n !== 'conditions'
              )
                return (
                  (O.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.areas !== void 0) {
                  let n = e.areas,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (g(n[r], {
                            instancePath: t + '/areas/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? g.errors : o.concat(g.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (O.errors = [
                          {
                            instancePath: t + '/areas',
                            schemaPath: '#/properties/areas/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.tasks !== void 0) {
                    let n = e.tasks,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        let e = n.length;
                        for (let r = 0; r < e; r++) {
                          let e = c;
                          if (
                            (x(n[r], {
                              instancePath: t + '/tasks/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? x.errors : o.concat(x.errors)), (c = o.length)),
                            e !== c)
                          )
                            break;
                        }
                      } else
                        return (
                          (O.errors = [
                            {
                              instancePath: t + '/tasks',
                              schemaPath: '#/properties/tasks/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.capabilities !== void 0) {
                      let n = e.capabilities,
                        r = c;
                      if (c === r) {
                        if (Array.isArray(n)) {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (C(n[r], {
                                instancePath: t + '/capabilities/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? C.errors : o.concat(C.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        } else
                          return (
                            (O.errors = [
                              {
                                instancePath: t + '/capabilities',
                                schemaPath: '#/properties/capabilities/type',
                                keyword: 'type',
                                params: { type: 'array' },
                                message: 'must be array',
                              },
                            ]),
                            !1
                          );
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.task_links !== void 0) {
                        let n = e.task_links,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (w(n[r], {
                                  instancePath: t + '/task_links/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? w.errors : o.concat(w.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (O.errors = [
                                {
                                  instancePath: t + '/task_links',
                                  schemaPath: '#/properties/task_links/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.collaborators !== void 0) {
                          let n = e.collaborators,
                            r = c;
                          if (c === r) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (T(n[r], {
                                    instancePath: t + '/collaborators/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? T.errors : o.concat(T.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else
                              return (
                                (O.errors = [
                                  {
                                    instancePath: t + '/collaborators',
                                    schemaPath: '#/properties/collaborators/type',
                                    keyword: 'type',
                                    params: { type: 'array' },
                                    message: 'must be array',
                                  },
                                ]),
                                !1
                              );
                          }
                          var u = r === c;
                        } else var u = !0;
                        if (u) {
                          if (e.conditions !== void 0) {
                            let n = e.conditions,
                              r = c;
                            if (c === r) {
                              if (Array.isArray(n)) {
                                let e = n.length;
                                for (let r = 0; r < e; r++) {
                                  let e = c;
                                  if (
                                    (D(n[r], {
                                      instancePath: t + '/conditions/' + r,
                                      parentData: n,
                                      parentDataProperty: r,
                                      rootData: i,
                                      dynamicAnchors: a,
                                    }) ||
                                      ((o = o === null ? D.errors : o.concat(D.errors)),
                                      (c = o.length)),
                                    e !== c)
                                  )
                                    break;
                                }
                              } else
                                return (
                                  (O.errors = [
                                    {
                                      instancePath: t + '/conditions',
                                      schemaPath: '#/properties/conditions/type',
                                      keyword: 'type',
                                      params: { type: 'array' },
                                      message: 'must be array',
                                    },
                                  ]),
                                  !1
                                );
                            }
                            var u = r === c;
                          } else var u = !0;
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (O.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((O.errors = o), c === 0);
    }
    O.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function ae(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ae.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.profile === void 0 && (n = 'profile')) || (e.work === void 0 && (n = 'work')))
            return (
              (ae.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'profile' && n !== 'work')
                return (
                  (ae.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.profile !== void 0) {
                let n = s;
                y(e.profile, {
                  instancePath: t + '/profile',
                  parentData: e,
                  parentDataProperty: 'profile',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? y.errors : o.concat(y.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.work !== void 0) {
                  let n = s;
                  O(e.work, {
                    instancePath: t + '/work',
                    parentData: e,
                    parentDataProperty: 'work',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? O.errors : o.concat(O.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (ae.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ae.errors = o), s === 0);
    }
    ((ae.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCapability = oe));
    function oe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = oe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.description === void 0 && (n = 'description'))
          )
            return (
              (oe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'capability_id' && n !== 'kind' && n !== 'name' && n !== 'description')
                return (
                  (oe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.capability_id !== void 0) {
                let n = c;
                s(e.capability_id, {
                  instancePath: t + '/capability_id',
                  parentData: e,
                  parentDataProperty: 'capability_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.kind !== void 0) {
                  let n = c;
                  S(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? S.errors : o.concat(S.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.name !== void 0) {
                    let n = e.name,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = s === c;
                    a ||= d;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = l === c;
                    if (((a ||= d), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (oe.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = c,
                        i = c,
                        a = !1,
                        s = c;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = s === c;
                      a ||= f;
                      let l = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = l === c;
                      if (((a ||= f), a))
                        ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (oe.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (oe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((oe.errors = o), c === 0);
    }
    ((oe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCapabilityField = ce));
    var se = {
      type: 'string',
      enum: ['name', 'description'],
      title: 'CapabilityField',
    };
    function ce(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = ce.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'name' && e !== 'description'
            ? ((ce.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: se.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((ce.errors = null), !0)
          : ((ce.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((ce.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCapabilityKind = le));
    function le(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = le.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'knowledge' && e !== 'skill'
            ? ((le.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: re.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((le.errors = null), !0)
          : ((le.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((le.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isClearField = de));
    var ue = {
      type: 'string',
      enum: ['job_title', 'organization_unit', 'reports_to', 'purpose'],
      title: 'ProfileField',
    };
    function k(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = k.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'job_title' && e !== 'organization_unit' && e !== 'reports_to' && e !== 'purpose'
            ? ((k.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: ue.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((k.errors = null), !0)
          : ((k.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    k.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function de(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = de.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.action === void 0 && (n = 'action')) || (e.field === void 0 && (n = 'field')))
            return (
              (de.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'field')
                return (
                  (de.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (de.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'clear_field')
                  return (
                    (de.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'clear_field' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.field !== void 0) {
                  let n = s;
                  k(e.field, {
                    instancePath: t + '/field',
                    parentData: e,
                    parentDataProperty: 'field',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? k.errors : o.concat(k.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (de.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((de.errors = o), s === 0);
    }
    ((de.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCollaborator = fe));
    function fe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = fe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.scope_text === void 0 && (n = 'scope_text'))
          )
            return (
              (fe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'collaborator_id' && n !== 'name' && n !== 'scope_text')
                return (
                  (fe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.collaborator_id !== void 0) {
                let n = c;
                s(e.collaborator_id, {
                  instancePath: t + '/collaborator_id',
                  parentData: e,
                  parentDataProperty: 'collaborator_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.name !== void 0) {
                  let n = e.name,
                    r = c,
                    i = c,
                    a = !1,
                    s = c;
                  if (typeof n != 'string') {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf/0/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = s === c;
                  a ||= d;
                  let l = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = l === c;
                  if (((a ||= d), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (fe.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.scope_text !== void 0) {
                    let n = e.scope_text,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = s === c;
                    a ||= f;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = l === c;
                    if (((a ||= f), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (fe.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (fe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((fe.errors = o), c === 0);
    }
    ((fe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCollaboratorField = me));
    var pe = {
      type: 'string',
      enum: ['name', 'scope_text'],
      title: 'CollaboratorField',
    };
    function me(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = me.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'name' && e !== 'scope_text'
            ? ((me.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: pe.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((me.errors = null), !0)
          : ((me.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((me.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCollaboratorFieldChange = he));
    function he(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = he.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (he.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (he.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = s;
                me(e.field, {
                  instancePath: t + '/field',
                  parentData: e,
                  parentDataProperty: 'field',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? me.errors : o.concat(me.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = e.value,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (he.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (he.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((he.errors = o), s === 0);
    }
    ((he.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCommentaryUpdate = ge));
    function ge(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = ge.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_file_id === void 0 && (n = 'job_file_id')) ||
            (e.execution_id === void 0 && (n = 'execution_id')) ||
            (e.response_id === void 0 && (n = 'response_id')) ||
            (e.message_id === void 0 && (n = 'message_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (ge.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'job_file_id' &&
                n !== 'execution_id' &&
                n !== 'response_id' &&
                n !== 'message_id' &&
                n !== 'text'
              )
                return (
                  (ge.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.job_file_id !== void 0) {
                let n = c;
                s(e.job_file_id, {
                  instancePath: t + '/job_file_id',
                  parentData: e,
                  parentDataProperty: 'job_file_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.execution_id !== void 0) {
                  let n = c;
                  s(e.execution_id, {
                    instancePath: t + '/execution_id',
                    parentData: e,
                    parentDataProperty: 'execution_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.response_id !== void 0) {
                    let n = c;
                    if (typeof e.response_id != 'string')
                      return (
                        (ge.errors = [
                          {
                            instancePath: t + '/response_id',
                            schemaPath: '#/properties/response_id/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.message_id !== void 0) {
                      let n = c;
                      if (typeof e.message_id != 'string')
                        return (
                          (ge.errors = [
                            {
                              instancePath: t + '/message_id',
                              schemaPath: '#/properties/message_id/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.text !== void 0) {
                        let n = c;
                        if (typeof e.text != 'string')
                          return (
                            (ge.errors = [
                              {
                                instancePath: t + '/text',
                                schemaPath: '#/properties/text/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              },
                            ]),
                            !1
                          );
                        var u = n === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (ge.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ge.errors = o), c === 0);
    }
    ((ge.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCondition = _e));
    function _e(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = _e.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (_e.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'condition_id' && n !== 'kind' && n !== 'text')
                return (
                  (_e.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.condition_id !== void 0) {
                let n = c;
                s(e.condition_id, {
                  instancePath: t + '/condition_id',
                  parentData: e,
                  parentDataProperty: 'condition_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.kind !== void 0) {
                  let n = c;
                  E(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? E.errors : o.concat(E.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.text !== void 0) {
                    let n = c;
                    if (typeof e.text != 'string')
                      return (
                        (_e.errors = [
                          {
                            instancePath: t + '/text',
                            schemaPath: '#/properties/text/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (_e.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((_e.errors = o), c === 0);
    }
    ((_e.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isConditionKind = ve));
    function ve(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = ve.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'work_environment' &&
            e !== 'schedule_travel' &&
            e !== 'shared_authority' &&
            e !== 'shared_collaboration' &&
            e !== 'qualification'
            ? ((ve.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: ie.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((ve.errors = null), !0)
          : ((ve.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((ve.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isConditionKindChange = A));
    function A(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = A.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (A.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (A.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = e.field,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (A.errors = [
                      {
                        instancePath: t + '/field',
                        schemaPath: '#/properties/field/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'kind')
                  return (
                    (A.errors = [
                      {
                        instancePath: t + '/field',
                        schemaPath: '#/properties/field/const',
                        keyword: 'const',
                        params: { allowedValue: 'kind' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = s;
                  E(e.value, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? E.errors : o.concat(E.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (A.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((A.errors = o), s === 0);
    }
    ((A.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isConditionTextChange = j));
    function j(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = j.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (j.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (j.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = e.field,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (j.errors = [
                      {
                        instancePath: t + '/field',
                        schemaPath: '#/properties/field/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'text')
                  return (
                    (j.errors = [
                      {
                        instancePath: t + '/field',
                        schemaPath: '#/properties/field/const',
                        keyword: 'const',
                        params: { allowedValue: 'text' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = s;
                  f(e.value, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (j.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((j.errors = o), s === 0);
    }
    ((j.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isConsultantTurn = N));
    var ye = {
        properties: {
          job_file_id: { $ref: '#/components/schemas/WireUuid' },
          execution_id: { $ref: '#/components/schemas/WireUuid' },
          status: { $ref: '#/components/schemas/ExecutionStatus' },
          pause_requested: {
            type: 'boolean',
            title: 'Pause Requested',
          },
          input_text: { $ref: '#/components/schemas/NonemptyText' },
          commentary: {
            anyOf: [
              {
                items: { $ref: '#/components/schemas/PublicCommentary' },
                type: 'array',
              },
              { type: 'null' },
            ],
            title: 'Commentary',
          },
          candidate: {
            anyOf: [{ $ref: '#/components/schemas/CandidateJdPreview' }, { type: 'null' }],
          },
          plan_preview: {
            anyOf: [{ $ref: '#/components/schemas/InterviewPlan' }, { type: 'null' }],
          },
          allowed_controls: {
            items: { $ref: '#/components/schemas/AllowedControl' },
            type: 'array',
            maxItems: 3,
            uniqueItems: !0,
            title: 'Allowed Controls',
          },
        },
        additionalProperties: !1,
        type: 'object',
        required: [
          'job_file_id',
          'execution_id',
          'status',
          'pause_requested',
          'input_text',
          'commentary',
          'candidate',
          'plan_preview',
          'allowed_controls',
        ],
        title: 'ConsultantTurn',
      },
      be = Object.prototype.hasOwnProperty,
      xe = r().default,
      Se = {
        type: 'string',
        enum: ['active', 'paused', 'completed', 'cancelled', 'failed'],
        title: 'ExecutionStatus',
      };
    function Ce(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Ce.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'active' &&
            e !== 'paused' &&
            e !== 'completed' &&
            e !== 'cancelled' &&
            e !== 'failed'
            ? ((Ce.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Se.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Ce.errors = null), !0)
          : ((Ce.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    Ce.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function M(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = M.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) < 1)
          return (
            (M.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
      } else
        return (
          (M.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((M.errors = null), !0);
    }
    M.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function we(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = we.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.response_id === void 0 && (n = 'response_id')) ||
            (e.message_id === void 0 && (n = 'message_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (we.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'response_id' && n !== 'message_id' && n !== 'text')
                return (
                  (we.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.response_id !== void 0) {
                let n = s;
                M(e.response_id, {
                  instancePath: t + '/response_id',
                  parentData: e,
                  parentDataProperty: 'response_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.message_id !== void 0) {
                  let n = s;
                  M(e.message_id, {
                    instancePath: t + '/message_id',
                    parentData: e,
                    parentDataProperty: 'message_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.text !== void 0) {
                    let n = s;
                    M(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (we.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((we.errors = o), s === 0);
    }
    we.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Te(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Te.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.plan === void 0 && (n = 'plan'))
            return (
              (Te.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'plan')
                return (
                  (Te.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s && e.plan !== void 0) {
              let n = e.plan,
                r = s,
                i = !1,
                a = s;
              if (typeof n != 'string') {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf/0/type',
                  keyword: 'type',
                  params: { type: 'string' },
                  message: 'must be string',
                };
                (o === null ? (o = [e]) : o.push(e), s++);
              }
              var l = a === s;
              i ||= l;
              let c = s;
              if (n !== null) {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf/1/type',
                  keyword: 'type',
                  params: { type: 'null' },
                  message: 'must be null',
                };
                (o === null ? (o = [e]) : o.push(e), s++);
              }
              var l = c === s;
              if (((i ||= l), i)) ((s = r), o !== null && (r ? (o.length = r) : (o = null)));
              else {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf',
                  keyword: 'anyOf',
                  params: {},
                  message: 'must match a schema in anyOf',
                };
                return (o === null ? (o = [e]) : o.push(e), s++, (Te.errors = o), !1);
              }
            }
          }
        } else
          return (
            (Te.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Te.errors = o), s === 0);
    }
    Te.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function N(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = N.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_file_id === void 0 && (n = 'job_file_id')) ||
            (e.execution_id === void 0 && (n = 'execution_id')) ||
            (e.status === void 0 && (n = 'status')) ||
            (e.pause_requested === void 0 && (n = 'pause_requested')) ||
            (e.input_text === void 0 && (n = 'input_text')) ||
            (e.commentary === void 0 && (n = 'commentary')) ||
            (e.candidate === void 0 && (n = 'candidate')) ||
            (e.plan_preview === void 0 && (n = 'plan_preview')) ||
            (e.allowed_controls === void 0 && (n = 'allowed_controls'))
          )
            return (
              (N.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (!be.call(ye.properties, n))
                return (
                  (N.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.job_file_id !== void 0) {
                let n = c;
                s(e.job_file_id, {
                  instancePath: t + '/job_file_id',
                  parentData: e,
                  parentDataProperty: 'job_file_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.execution_id !== void 0) {
                  let n = c;
                  s(e.execution_id, {
                    instancePath: t + '/execution_id',
                    parentData: e,
                    parentDataProperty: 'execution_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.status !== void 0) {
                    let n = c;
                    Ce(e.status, {
                      instancePath: t + '/status',
                      parentData: e,
                      parentDataProperty: 'status',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Ce.errors : o.concat(Ce.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.pause_requested !== void 0) {
                      let n = c;
                      if (typeof e.pause_requested != 'boolean')
                        return (
                          (N.errors = [
                            {
                              instancePath: t + '/pause_requested',
                              schemaPath: '#/properties/pause_requested/type',
                              keyword: 'type',
                              params: { type: 'boolean' },
                              message: 'must be boolean',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.input_text !== void 0) {
                        let n = c;
                        M(e.input_text, {
                          instancePath: t + '/input_text',
                          parentData: e,
                          parentDataProperty: 'input_text',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? M.errors : o.concat(M.errors)), (c = o.length));
                        var u = n === c;
                      } else var u = !0;
                      if (u) {
                        if (e.commentary !== void 0) {
                          let n = e.commentary,
                            r = c,
                            s = c,
                            l = !1,
                            f = c;
                          if (c === f) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (we(n[r], {
                                    instancePath: t + '/commentary/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? we.errors : o.concat(we.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else {
                              let e = {
                                instancePath: t + '/commentary',
                                schemaPath: '#/properties/commentary/anyOf/0/type',
                                keyword: 'type',
                                params: { type: 'array' },
                                message: 'must be array',
                              };
                              (o === null ? (o = [e]) : o.push(e), c++);
                            }
                          }
                          var d = f === c;
                          l ||= d;
                          let p = c;
                          if (n !== null) {
                            let e = {
                              instancePath: t + '/commentary',
                              schemaPath: '#/properties/commentary/anyOf/1/type',
                              keyword: 'type',
                              params: { type: 'null' },
                              message: 'must be null',
                            };
                            (o === null ? (o = [e]) : o.push(e), c++);
                          }
                          var d = p === c;
                          if (((l ||= d), l))
                            ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                          else {
                            let e = {
                              instancePath: t + '/commentary',
                              schemaPath: '#/properties/commentary/anyOf',
                              keyword: 'anyOf',
                              params: {},
                              message: 'must match a schema in anyOf',
                            };
                            return (o === null ? (o = [e]) : o.push(e), c++, (N.errors = o), !1);
                          }
                          var u = r === c;
                        } else var u = !0;
                        if (u) {
                          if (e.candidate !== void 0) {
                            let n = e.candidate,
                              r = c,
                              s = c,
                              l = !1,
                              d = c;
                            ae(n, {
                              instancePath: t + '/candidate',
                              parentData: e,
                              parentDataProperty: 'candidate',
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? ae.errors : o.concat(ae.errors)), (c = o.length));
                            var f = d === c;
                            l ||= f;
                            let p = c;
                            if (n !== null) {
                              let e = {
                                instancePath: t + '/candidate',
                                schemaPath: '#/properties/candidate/anyOf/1/type',
                                keyword: 'type',
                                params: { type: 'null' },
                                message: 'must be null',
                              };
                              (o === null ? (o = [e]) : o.push(e), c++);
                            }
                            var f = p === c;
                            if (((l ||= f), l))
                              ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                            else {
                              let e = {
                                instancePath: t + '/candidate',
                                schemaPath: '#/properties/candidate/anyOf',
                                keyword: 'anyOf',
                                params: {},
                                message: 'must match a schema in anyOf',
                              };
                              return (o === null ? (o = [e]) : o.push(e), c++, (N.errors = o), !1);
                            }
                            var u = r === c;
                          } else var u = !0;
                          if (u) {
                            if (e.plan_preview !== void 0) {
                              let n = e.plan_preview,
                                r = c,
                                s = c,
                                l = !1,
                                d = c;
                              Te(n, {
                                instancePath: t + '/plan_preview',
                                parentData: e,
                                parentDataProperty: 'plan_preview',
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? Te.errors : o.concat(Te.errors)),
                                (c = o.length));
                              var p = d === c;
                              l ||= p;
                              let f = c;
                              if (n !== null) {
                                let e = {
                                  instancePath: t + '/plan_preview',
                                  schemaPath: '#/properties/plan_preview/anyOf/1/type',
                                  keyword: 'type',
                                  params: { type: 'null' },
                                  message: 'must be null',
                                };
                                (o === null ? (o = [e]) : o.push(e), c++);
                              }
                              var p = f === c;
                              if (((l ||= p), l))
                                ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                              else {
                                let e = {
                                  instancePath: t + '/plan_preview',
                                  schemaPath: '#/properties/plan_preview/anyOf',
                                  keyword: 'anyOf',
                                  params: {},
                                  message: 'must match a schema in anyOf',
                                };
                                return (
                                  o === null ? (o = [e]) : o.push(e),
                                  c++,
                                  (N.errors = o),
                                  !1
                                );
                              }
                              var u = r === c;
                            } else var u = !0;
                            if (u) {
                              if (e.allowed_controls !== void 0) {
                                let n = e.allowed_controls,
                                  r = c;
                                if (c === r) {
                                  if (Array.isArray(n)) {
                                    if (n.length > 3)
                                      return (
                                        (N.errors = [
                                          {
                                            instancePath: t + '/allowed_controls',
                                            schemaPath: '#/properties/allowed_controls/maxItems',
                                            keyword: 'maxItems',
                                            params: { limit: 3 },
                                            message: 'must NOT have more than 3 items',
                                          },
                                        ]),
                                        !1
                                      );
                                    {
                                      var m = !0;
                                      let e = n.length;
                                      for (let r = 0; r < e; r++) {
                                        let e = c;
                                        h(n[r], {
                                          instancePath: t + '/allowed_controls/' + r,
                                          parentData: n,
                                          parentDataProperty: r,
                                          rootData: i,
                                          dynamicAnchors: a,
                                        }) ||
                                          ((o = o === null ? h.errors : o.concat(h.errors)),
                                          (c = o.length));
                                        var m = e === c;
                                        if (!m) break;
                                      }
                                      if (m) {
                                        let e = n.length,
                                          r;
                                        if (e > 1) {
                                          outer0: for (; e--;)
                                            for (r = e; r--;)
                                              if (xe(n[e], n[r]))
                                                return (
                                                  (N.errors = [
                                                    {
                                                      instancePath: t + '/allowed_controls',
                                                      schemaPath:
                                                        '#/properties/allowed_controls/uniqueItems',
                                                      keyword: 'uniqueItems',
                                                      params: {
                                                        i: e,
                                                        j: r,
                                                      },
                                                      message:
                                                        'must NOT have duplicate items (items ## ' +
                                                        r +
                                                        ' and ' +
                                                        e +
                                                        ' are identical)',
                                                    },
                                                  ]),
                                                  !1
                                                );
                                        }
                                      }
                                    }
                                  } else
                                    return (
                                      (N.errors = [
                                        {
                                          instancePath: t + '/allowed_controls',
                                          schemaPath: '#/properties/allowed_controls/type',
                                          keyword: 'type',
                                          params: { type: 'array' },
                                          message: 'must be array',
                                        },
                                      ]),
                                      !1
                                    );
                                }
                                var u = r === c;
                              } else var u = !0;
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (N.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((N.errors = o), c === 0);
    }
    ((N.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateArea = P));
    function P(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = P.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.scope_text === void 0 && (n = 'scope_text'))
          )
            return (
              (P.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'title' && n !== 'scope_text')
                return (
                  (P.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (P.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'create_area')
                  return (
                    (P.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'create_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.title !== void 0) {
                  let n = e.title,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/title',
                    parentData: e,
                    parentDataProperty: 'title',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/title',
                      schemaPath: '#/properties/title/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/title',
                      schemaPath: '#/properties/title/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (P.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
                if (l) {
                  if (e.scope_text !== void 0) {
                    let n = e.scope_text,
                      r = s,
                      c = s,
                      u = !1,
                      p = s;
                    f(n, {
                      instancePath: t + '/scope_text',
                      parentData: e,
                      parentDataProperty: 'scope_text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var d = p === s;
                    u ||= d;
                    let m = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var d = m === s;
                    if (((u ||= d), u)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (P.errors = o), !1);
                    }
                    var l = r === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (P.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((P.errors = o), s === 0);
    }
    ((P.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateCapability = F));
    function F(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = F.evaluated;
      (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0));
      let l = s,
        u = !1,
        d = s;
      if (
        e &&
        typeof e == 'object' &&
        !Array.isArray(e) &&
        e.name !== void 0 &&
        typeof e.name != 'string'
      ) {
        let e = {
          instancePath: t + '/name',
          schemaPath: '#/anyOf/0/properties/name/type',
          keyword: 'type',
          params: { type: 'string' },
          message: 'must be string',
        };
        (o === null ? (o = [e]) : o.push(e), s++);
      }
      var p = d === s;
      if (((u ||= p), p)) {
        var m = {};
        m.name = !0;
      }
      let h = s;
      if (
        e &&
        typeof e == 'object' &&
        !Array.isArray(e) &&
        e.description !== void 0 &&
        typeof e.description != 'string'
      ) {
        let e = {
          instancePath: t + '/description',
          schemaPath: '#/anyOf/1/properties/description/type',
          keyword: 'type',
          params: { type: 'string' },
          message: 'must be string',
        };
        (o === null ? (o = [e]) : o.push(e), s++);
      }
      var p = h === s;
      if (((u ||= p), p && m !== !0 && ((m ||= {}), (m.description = !0)), u))
        ((s = l), o !== null && (l ? (o.length = l) : (o = null)));
      else {
        let e = {
          instancePath: t,
          schemaPath: '#/anyOf',
          keyword: 'anyOf',
          params: {},
          message: 'must match a schema in anyOf',
        };
        return (o === null ? (o = [e]) : o.push(e), s++, (F.errors = o), !1);
      }
      if (s === 0) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.description === void 0 && (n = 'description'))
          )
            return (
              (F.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'kind' && n !== 'name' && n !== 'description')
                return (
                  (F.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (F.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'create_capability')
                  return (
                    (F.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'create_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var g = r === s;
              } else var g = !0;
              if (g) {
                if (e.kind !== void 0) {
                  let n = s;
                  S(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? S.errors : o.concat(S.errors)), (s = o.length));
                  var g = n === s;
                } else var g = !0;
                if (g) {
                  if (e.name !== void 0) {
                    let n = e.name,
                      r = s,
                      c = s,
                      l = !1,
                      u = s;
                    f(n, {
                      instancePath: t + '/name',
                      parentData: e,
                      parentDataProperty: 'name',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var ee = u === s;
                    l ||= ee;
                    let d = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var ee = d === s;
                    if (((l ||= ee), l)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/name',
                        schemaPath: '#/properties/name/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (F.errors = o), !1);
                    }
                    var g = r === s;
                  } else var g = !0;
                  if (g) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = s,
                        c = s,
                        l = !1,
                        u = s;
                      f(n, {
                        instancePath: t + '/description',
                        parentData: e,
                        parentDataProperty: 'description',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                      var te = u === s;
                      l ||= te;
                      let d = s;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), s++);
                      }
                      var te = d === s;
                      if (((l ||= te), l))
                        ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), s++, (F.errors = o), !1);
                      }
                      var g = r === s;
                    } else var g = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (F.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((F.errors = o), s === 0);
    }
    ((F.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateCollaborator = I));
    function I(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = I.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.name === void 0 && (n = 'name')) ||
            (e.scope_text === void 0 && (n = 'scope_text'))
          )
            return (
              (I.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'name' && n !== 'scope_text')
                return (
                  (I.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (I.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'create_collaborator')
                  return (
                    (I.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'create_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.name !== void 0) {
                  let n = e.name,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/name',
                    parentData: e,
                    parentDataProperty: 'name',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/name',
                      schemaPath: '#/properties/name/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (I.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
                if (l) {
                  if (e.scope_text !== void 0) {
                    let n = e.scope_text,
                      r = s,
                      c = s,
                      u = !1,
                      p = s;
                    f(n, {
                      instancePath: t + '/scope_text',
                      parentData: e,
                      parentDataProperty: 'scope_text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var d = p === s;
                    u ||= d;
                    let m = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var d = m === s;
                    if (((u ||= d), u)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/scope_text',
                        schemaPath: '#/properties/scope_text/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (I.errors = o), !1);
                    }
                    var l = r === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (I.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((I.errors = o), s === 0);
    }
    ((I.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateCondition = Ee));
    function Ee(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Ee.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (Ee.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'kind' && n !== 'text')
                return (
                  (Ee.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (Ee.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'create_condition')
                  return (
                    (Ee.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'create_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.kind !== void 0) {
                  let n = s;
                  E(e.kind, {
                    instancePath: t + '/kind',
                    parentData: e,
                    parentDataProperty: 'kind',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? E.errors : o.concat(E.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.text !== void 0) {
                    let n = s;
                    f(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (Ee.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ee.errors = o), s === 0);
    }
    ((Ee.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateJobFileRequest = De));
    function L(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = L.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) > 200)
          return (
            (L.errors = [
              {
                instancePath: t,
                schemaPath: '#/maxLength',
                keyword: 'maxLength',
                params: { limit: 200 },
                message: 'must NOT have more than 200 characters',
              },
            ]),
            !1
          );
        if (a(e) < 1)
          return (
            (L.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
        if (!d.test(e))
          return (
            (L.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$',
                },
                message:
                  'must match pattern "^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$"',
              },
            ]),
            !1
          );
      } else
        return (
          (L.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((L.errors = null), !0);
    }
    L.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function De(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = De.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.display_name === void 0 && (n = 'display_name')) ||
            (e.employee_name === void 0 && (n = 'employee_name'))
          )
            return (
              (De.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'display_name' && n !== 'employee_name')
                return (
                  (De.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.display_name !== void 0) {
                  let n = c;
                  L(e.display_name, {
                    instancePath: t + '/display_name',
                    parentData: e,
                    parentDataProperty: 'display_name',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? L.errors : o.concat(L.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.employee_name !== void 0) {
                    let n = c;
                    L(e.employee_name, {
                      instancePath: t + '/employee_name',
                      parentData: e,
                      parentDataProperty: 'employee_name',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? L.errors : o.concat(L.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (De.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((De.errors = o), c === 0);
    }
    ((De.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCreateTask = R));
    function R(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = R.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.outcomes === void 0 && (n = 'outcomes')) ||
            (e.requirements === void 0 && (n = 'requirements'))
          )
            return (
              (R.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'area_id' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'outcomes' &&
                n !== 'requirements'
              )
                return (
                  (R.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (R.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'create_task')
                  return (
                    (R.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'create_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = e.area_id,
                    r = c,
                    l = c,
                    f = !1,
                    p = c;
                  s(n, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = p === c;
                  f ||= d;
                  let m = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = m === c;
                  if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (R.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.title !== void 0) {
                    let n = e.title,
                      r = c,
                      s = c,
                      l = !1,
                      d = c;
                    f(n, {
                      instancePath: t + '/title',
                      parentData: e,
                      parentDataProperty: 'title',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (c = o.length));
                    var p = d === c;
                    l ||= p;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var p = m === c;
                    if (((l ||= p), l)) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (R.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = c,
                        s = c,
                        l = !1,
                        d = c;
                      f(n, {
                        instancePath: t + '/description',
                        parentData: e,
                        parentDataProperty: 'description',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? f.errors : o.concat(f.errors)), (c = o.length));
                      var m = d === c;
                      l ||= m;
                      let p = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var m = p === c;
                      if (((l ||= m), l))
                        ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (R.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.outcomes !== void 0) {
                        let n = e.outcomes,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (f(n[r], {
                                  instancePath: t + '/outcomes/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? f.errors : o.concat(f.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (R.errors = [
                                {
                                  instancePath: t + '/outcomes',
                                  schemaPath: '#/properties/outcomes/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.requirements !== void 0) {
                          let n = e.requirements,
                            r = c;
                          if (c === r) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (f(n[r], {
                                    instancePath: t + '/requirements/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? f.errors : o.concat(f.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else
                              return (
                                (R.errors = [
                                  {
                                    instancePath: t + '/requirements',
                                    schemaPath: '#/properties/requirements/type',
                                    keyword: 'type',
                                    params: { type: 'array' },
                                    message: 'must be array',
                                  },
                                ]),
                                !1
                              );
                          }
                          var u = r === c;
                        } else var u = !0;
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (R.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((R.errors = o), c === 0);
    }
    ((R.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isCurrentConsultantTurn = Oe));
    function Oe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Oe.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.turn === void 0 && (n = 'turn'))
            return (
              (Oe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'turn')
                return (
                  (Oe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s && e.turn !== void 0) {
              let n = e.turn,
                r = s,
                c = !1,
                u = s;
              N(n, {
                instancePath: t + '/turn',
                parentData: e,
                parentDataProperty: 'turn',
                rootData: i,
                dynamicAnchors: a,
              }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length));
              var l = u === s;
              c ||= l;
              let d = s;
              if (n !== null) {
                let e = {
                  instancePath: t + '/turn',
                  schemaPath: '#/properties/turn/anyOf/1/type',
                  keyword: 'type',
                  params: { type: 'null' },
                  message: 'must be null',
                };
                (o === null ? (o = [e]) : o.push(e), s++);
              }
              var l = d === s;
              if (((c ||= l), c)) ((s = r), o !== null && (r ? (o.length = r) : (o = null)));
              else {
                let e = {
                  instancePath: t + '/turn',
                  schemaPath: '#/properties/turn/anyOf',
                  keyword: 'anyOf',
                  params: {},
                  message: 'must match a schema in anyOf',
                };
                return (o === null ? (o = [e]) : o.push(e), s++, (Oe.errors = o), !1);
              }
            }
          }
        } else
          return (
            (Oe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Oe.errors = o), s === 0);
    }
    ((Oe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDeleteArea = ke));
    function ke(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = ke.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.action === void 0 && (n = 'action')) || (e.area_id === void 0 && (n = 'area_id')))
            return (
              (ke.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'area_id')
                return (
                  (ke.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (ke.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'delete_area')
                  return (
                    (ke.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'delete_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = c;
                  s(e.area_id, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (ke.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ke.errors = o), c === 0);
    }
    ((ke.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDeleteCapability = Ae));
    function Ae(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ae.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.capability_id === void 0 && (n = 'capability_id'))
          )
            return (
              (Ae.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'capability_id')
                return (
                  (Ae.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Ae.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'delete_capability')
                  return (
                    (Ae.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'delete_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Ae.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ae.errors = o), c === 0);
    }
    ((Ae.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDeleteCollaborator = je));
    function je(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = je.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.collaborator_id === void 0 && (n = 'collaborator_id'))
          )
            return (
              (je.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'collaborator_id')
                return (
                  (je.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (je.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'delete_collaborator')
                  return (
                    (je.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'delete_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.collaborator_id !== void 0) {
                  let n = c;
                  s(e.collaborator_id, {
                    instancePath: t + '/collaborator_id',
                    parentData: e,
                    parentDataProperty: 'collaborator_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (je.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((je.errors = o), c === 0);
    }
    ((je.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDeleteCondition = Me));
    function Me(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Me.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.condition_id === void 0 && (n = 'condition_id'))
          )
            return (
              (Me.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'condition_id')
                return (
                  (Me.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Me.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'delete_condition')
                  return (
                    (Me.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'delete_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.condition_id !== void 0) {
                  let n = c;
                  s(e.condition_id, {
                    instancePath: t + '/condition_id',
                    parentData: e,
                    parentDataProperty: 'condition_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Me.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Me.errors = o), c === 0);
    }
    ((Me.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDeleteTask = Ne));
    function Ne(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ne.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.action === void 0 && (n = 'action')) || (e.task_id === void 0 && (n = 'task_id')))
            return (
              (Ne.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'task_id')
                return (
                  (Ne.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Ne.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'delete_task')
                  return (
                    (Ne.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'delete_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Ne.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ne.errors = o), c === 0);
    }
    ((Ne.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDetail = Pe));
    function Pe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Pe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.detail_id === void 0 && (n = 'detail_id')) || (e.text === void 0 && (n = 'text')))
            return (
              (Pe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'detail_id' && n !== 'text')
                return (
                  (Pe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.detail_id !== void 0) {
                let n = c;
                s(e.detail_id, {
                  instancePath: t + '/detail_id',
                  parentData: e,
                  parentDataProperty: 'detail_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.text !== void 0) {
                  let n = c;
                  if (typeof e.text != 'string')
                    return (
                      (Pe.errors = [
                        {
                          instancePath: t + '/text',
                          schemaPath: '#/properties/text/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Pe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Pe.errors = o), c === 0);
    }
    ((Pe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDetailKind = Fe));
    function Fe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Fe.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'outcome' && e !== 'requirement'
            ? ((Fe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: l.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Fe.errors = null), !0)
          : ((Fe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((Fe.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isDisplayName = Ie));
    function Ie(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = Ie.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) > 200)
          return (
            (Ie.errors = [
              {
                instancePath: t,
                schemaPath: '#/maxLength',
                keyword: 'maxLength',
                params: { limit: 200 },
                message: 'must NOT have more than 200 characters',
              },
            ]),
            !1
          );
        if (a(e) < 1)
          return (
            (Ie.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
        if (!d.test(e))
          return (
            (Ie.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$',
                },
                message:
                  'must match pattern "^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$"',
              },
            ]),
            !1
          );
      } else
        return (
          (Ie.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((Ie.errors = null), !0);
    }
    ((Ie.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isEditJdAreasRequest = Re));
    function z(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = z.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (z.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'area_id' && n !== 'changes')
                return (
                  (z.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (z.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_area')
                  return (
                    (z.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = c;
                  s(e.area_id, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (z.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (z.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (_(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? _.errors : o.concat(_.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (z.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (z.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((z.errors = o), c === 0);
    }
    z.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Le(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Le.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.before_area_id === void 0 && (n = 'before_area_id'))
          )
            return (
              (Le.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'area_id' && n !== 'before_area_id')
                return (
                  (Le.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Le.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_area')
                  return (
                    (Le.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = c;
                  s(e.area_id, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_area_id !== void 0) {
                    let n = e.before_area_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_area_id',
                      parentData: e,
                      parentDataProperty: 'before_area_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_area_id',
                        schemaPath: '#/properties/before_area_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_area_id',
                        schemaPath: '#/properties/before_area_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Le.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Le.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Le.errors = o), c === 0);
    }
    Le.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Re(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Re.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.change === void 0 && (n = 'change'))
          )
            return (
              (Re.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'change')
                return (
                  (Re.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.change !== void 0) {
                    let n = e.change,
                      r = c,
                      s = c,
                      l = !1,
                      p = null,
                      m = c;
                    P(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? P.errors : o.concat(P.errors)), (c = o.length));
                    var d = m === c;
                    if (d) {
                      ((l = !0), (p = 0));
                      var f = !0;
                    }
                    let h = c;
                    z(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? z.errors : o.concat(z.errors)), (c = o.length));
                    var d = h === c;
                    if (d && l) ((l = !1), (p = [p, 1]));
                    else {
                      d && ((l = !0), (p = 1), f !== !0 && (f = !0));
                      let r = c;
                      ke(n, {
                        instancePath: t + '/change',
                        parentData: e,
                        parentDataProperty: 'change',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? ke.errors : o.concat(ke.errors)), (c = o.length));
                      var d = r === c;
                      if (d && l) ((l = !1), (p = [p, 2]));
                      else {
                        d && ((l = !0), (p = 2), f !== !0 && (f = !0));
                        let r = c;
                        Le(n, {
                          instancePath: t + '/change',
                          parentData: e,
                          parentDataProperty: 'change',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? Le.errors : o.concat(Le.errors)), (c = o.length));
                        var d = r === c;
                        d && l
                          ? ((l = !1), (p = [p, 3]))
                          : d && ((l = !0), (p = 3), f !== !0 && (f = !0));
                      }
                    }
                    if (l) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/change',
                        schemaPath: '#/properties/change/oneOf',
                        keyword: 'oneOf',
                        params: { passingSchemas: p },
                        message: 'must match exactly one schema in oneOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Re.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Re.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Re.errors = o), c === 0);
    }
    ((Re.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isEditJdCapabilitiesRequest = Ue));
    function ze(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ze.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (ze.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (ze.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = s;
                ce(e.field, {
                  instancePath: t + '/field',
                  parentData: e,
                  parentDataProperty: 'field',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? ce.errors : o.concat(ce.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = e.value,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (ze.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (ze.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ze.errors = o), s === 0);
    }
    ze.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function B(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = B.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (B.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'capability_id' && n !== 'changes')
                return (
                  (B.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (B.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_capability')
                  return (
                    (B.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (B.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (B.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (ze(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? ze.errors : o.concat(ze.errors)),
                                (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (B.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (B.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((B.errors = o), c === 0);
    }
    B.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Be(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Be.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.before_capability_id === void 0 && (n = 'before_capability_id'))
          )
            return (
              (Be.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'capability_id' && n !== 'before_capability_id')
                return (
                  (Be.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Be.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_capability')
                  return (
                    (Be.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_capability_id !== void 0) {
                    let n = e.before_capability_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_capability_id',
                      parentData: e,
                      parentDataProperty: 'before_capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_capability_id',
                        schemaPath: '#/properties/before_capability_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_capability_id',
                        schemaPath: '#/properties/before_capability_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Be.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Be.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Be.errors = o), c === 0);
    }
    Be.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ve(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ve.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.linked === void 0 && (n = 'linked'))
          )
            return (
              (Ve.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'task_id' && n !== 'capability_id' && n !== 'linked')
                return (
                  (Ve.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Ve.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'set_task_capability')
                  return (
                    (Ve.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'set_task_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.capability_id !== void 0) {
                    let n = c;
                    s(e.capability_id, {
                      instancePath: t + '/capability_id',
                      parentData: e,
                      parentDataProperty: 'capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.linked !== void 0) {
                      let n = c;
                      if (typeof e.linked != 'boolean')
                        return (
                          (Ve.errors = [
                            {
                              instancePath: t + '/linked',
                              schemaPath: '#/properties/linked/type',
                              keyword: 'type',
                              params: { type: 'boolean' },
                              message: 'must be boolean',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (Ve.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ve.errors = o), c === 0);
    }
    Ve.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function He(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = He.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.before_capability_id === void 0 && (n = 'before_capability_id'))
          )
            return (
              (He.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'capability_id' &&
                n !== 'before_capability_id'
              )
                return (
                  (He.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (He.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_task_capability')
                  return (
                    (He.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_task_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.capability_id !== void 0) {
                    let n = c;
                    s(e.capability_id, {
                      instancePath: t + '/capability_id',
                      parentData: e,
                      parentDataProperty: 'capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_capability_id !== void 0) {
                      let n = e.before_capability_id,
                        r = c,
                        l = c,
                        f = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_capability_id',
                        parentData: e,
                        parentDataProperty: 'before_capability_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var d = p === c;
                      f ||= d;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_capability_id',
                          schemaPath: '#/properties/before_capability_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = m === c;
                      if (((f ||= d), f))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_capability_id',
                          schemaPath: '#/properties/before_capability_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (He.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (He.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((He.errors = o), c === 0);
    }
    He.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ue(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ue.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.change === void 0 && (n = 'change'))
          )
            return (
              (Ue.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'change')
                return (
                  (Ue.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.change !== void 0) {
                    let n = e.change,
                      r = c,
                      s = c,
                      l = !1,
                      p = null,
                      m = c;
                    F(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? F.errors : o.concat(F.errors)), (c = o.length));
                    var d = m === c;
                    if (d) {
                      ((l = !0), (p = 0));
                      var f = !0;
                    }
                    let h = c;
                    B(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? B.errors : o.concat(B.errors)), (c = o.length));
                    var d = h === c;
                    if (d && l) ((l = !1), (p = [p, 1]));
                    else {
                      d && ((l = !0), (p = 1), f !== !0 && (f = !0));
                      let r = c;
                      Ae(n, {
                        instancePath: t + '/change',
                        parentData: e,
                        parentDataProperty: 'change',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? Ae.errors : o.concat(Ae.errors)), (c = o.length));
                      var d = r === c;
                      if (d && l) ((l = !1), (p = [p, 2]));
                      else {
                        d && ((l = !0), (p = 2), f !== !0 && (f = !0));
                        let r = c;
                        Be(n, {
                          instancePath: t + '/change',
                          parentData: e,
                          parentDataProperty: 'change',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? Be.errors : o.concat(Be.errors)), (c = o.length));
                        var d = r === c;
                        if (d && l) ((l = !1), (p = [p, 3]));
                        else {
                          d && ((l = !0), (p = 3), f !== !0 && (f = !0));
                          let r = c;
                          Ve(n, {
                            instancePath: t + '/change',
                            parentData: e,
                            parentDataProperty: 'change',
                            rootData: i,
                            dynamicAnchors: a,
                          }) ||
                            ((o = o === null ? Ve.errors : o.concat(Ve.errors)), (c = o.length));
                          var d = r === c;
                          if (d && l) ((l = !1), (p = [p, 4]));
                          else {
                            d && ((l = !0), (p = 4), f !== !0 && (f = !0));
                            let r = c;
                            He(n, {
                              instancePath: t + '/change',
                              parentData: e,
                              parentDataProperty: 'change',
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? He.errors : o.concat(He.errors)), (c = o.length));
                            var d = r === c;
                            d && l
                              ? ((l = !1), (p = [p, 5]))
                              : d && ((l = !0), (p = 5), f !== !0 && (f = !0));
                          }
                        }
                      }
                    }
                    if (l) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/change',
                        schemaPath: '#/properties/change/oneOf',
                        keyword: 'oneOf',
                        params: { passingSchemas: p },
                        message: 'must match exactly one schema in oneOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Ue.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Ue.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ue.errors = o), c === 0);
    }
    ((Ue.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isEditJdCollaboratorsRequest = Ge));
    function V(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = V.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (V.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'collaborator_id' && n !== 'changes')
                return (
                  (V.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (V.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_collaborator')
                  return (
                    (V.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.collaborator_id !== void 0) {
                  let n = c;
                  s(e.collaborator_id, {
                    instancePath: t + '/collaborator_id',
                    parentData: e,
                    parentDataProperty: 'collaborator_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (V.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (V.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (he(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? he.errors : o.concat(he.errors)),
                                (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (V.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (V.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((V.errors = o), c === 0);
    }
    V.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function We(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = We.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.before_collaborator_id === void 0 && (n = 'before_collaborator_id'))
          )
            return (
              (We.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'collaborator_id' && n !== 'before_collaborator_id')
                return (
                  (We.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (We.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_collaborator')
                  return (
                    (We.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.collaborator_id !== void 0) {
                  let n = c;
                  s(e.collaborator_id, {
                    instancePath: t + '/collaborator_id',
                    parentData: e,
                    parentDataProperty: 'collaborator_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_collaborator_id !== void 0) {
                    let n = e.before_collaborator_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_collaborator_id',
                      parentData: e,
                      parentDataProperty: 'before_collaborator_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_collaborator_id',
                        schemaPath: '#/properties/before_collaborator_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_collaborator_id',
                        schemaPath: '#/properties/before_collaborator_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (We.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (We.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((We.errors = o), c === 0);
    }
    We.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ge(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ge.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.change === void 0 && (n = 'change'))
          )
            return (
              (Ge.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'change')
                return (
                  (Ge.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.change !== void 0) {
                    let n = e.change,
                      r = c,
                      s = c,
                      l = !1,
                      p = null,
                      m = c;
                    I(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? I.errors : o.concat(I.errors)), (c = o.length));
                    var d = m === c;
                    if (d) {
                      ((l = !0), (p = 0));
                      var f = !0;
                    }
                    let h = c;
                    V(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? V.errors : o.concat(V.errors)), (c = o.length));
                    var d = h === c;
                    if (d && l) ((l = !1), (p = [p, 1]));
                    else {
                      d && ((l = !0), (p = 1), f !== !0 && (f = !0));
                      let r = c;
                      je(n, {
                        instancePath: t + '/change',
                        parentData: e,
                        parentDataProperty: 'change',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? je.errors : o.concat(je.errors)), (c = o.length));
                      var d = r === c;
                      if (d && l) ((l = !1), (p = [p, 2]));
                      else {
                        d && ((l = !0), (p = 2), f !== !0 && (f = !0));
                        let r = c;
                        We(n, {
                          instancePath: t + '/change',
                          parentData: e,
                          parentDataProperty: 'change',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? We.errors : o.concat(We.errors)), (c = o.length));
                        var d = r === c;
                        d && l
                          ? ((l = !1), (p = [p, 3]))
                          : d && ((l = !0), (p = 3), f !== !0 && (f = !0));
                      }
                    }
                    if (l) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/change',
                        schemaPath: '#/properties/change/oneOf',
                        keyword: 'oneOf',
                        params: { passingSchemas: p },
                        message: 'must match exactly one schema in oneOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Ge.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Ge.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ge.errors = o), c === 0);
    }
    ((Ge.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isEditJdConditionsRequest = qe));
    function H(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = H.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (H.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'condition_id' && n !== 'changes')
                return (
                  (H.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (H.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_condition')
                  return (
                    (H.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.condition_id !== void 0) {
                  let n = c;
                  s(e.condition_id, {
                    instancePath: t + '/condition_id',
                    parentData: e,
                    parentDataProperty: 'condition_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (H.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (H.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = n[r],
                              s = c,
                              l = c,
                              u = !1,
                              p = null,
                              m = c;
                            j(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? j.errors : o.concat(j.errors)), (c = o.length));
                            var d = m === c;
                            if (d) {
                              ((u = !0), (p = 0));
                              var f = !0;
                            }
                            let h = c;
                            A(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? A.errors : o.concat(A.errors)), (c = o.length));
                            var d = h === c;
                            if (
                              (d && u
                                ? ((u = !1), (p = [p, 1]))
                                : d && ((u = !0), (p = 1), f !== !0 && (f = !0)),
                              u)
                            )
                              ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                            else {
                              let e = {
                                instancePath: t + '/changes/' + r,
                                schemaPath: '#/properties/changes/items/oneOf',
                                keyword: 'oneOf',
                                params: { passingSchemas: p },
                                message: 'must match exactly one schema in oneOf',
                              };
                              return (o === null ? (o = [e]) : o.push(e), c++, (H.errors = o), !1);
                            }
                            if (s !== c) break;
                          }
                        }
                      } else
                        return (
                          (H.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (H.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((H.errors = o), c === 0);
    }
    H.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ke(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ke.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.before_condition_id === void 0 && (n = 'before_condition_id'))
          )
            return (
              (Ke.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'condition_id' && n !== 'before_condition_id')
                return (
                  (Ke.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Ke.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_condition')
                  return (
                    (Ke.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.condition_id !== void 0) {
                  let n = c;
                  s(e.condition_id, {
                    instancePath: t + '/condition_id',
                    parentData: e,
                    parentDataProperty: 'condition_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_condition_id !== void 0) {
                    let n = e.before_condition_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_condition_id',
                      parentData: e,
                      parentDataProperty: 'before_condition_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_condition_id',
                        schemaPath: '#/properties/before_condition_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_condition_id',
                        schemaPath: '#/properties/before_condition_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Ke.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Ke.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ke.errors = o), c === 0);
    }
    Ke.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function qe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = qe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.change === void 0 && (n = 'change'))
          )
            return (
              (qe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'change')
                return (
                  (qe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.change !== void 0) {
                    let n = e.change,
                      r = c,
                      s = c,
                      l = !1,
                      p = null,
                      m = c;
                    Ee(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Ee.errors : o.concat(Ee.errors)), (c = o.length));
                    var d = m === c;
                    if (d) {
                      ((l = !0), (p = 0));
                      var f = !0;
                    }
                    let h = c;
                    H(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? H.errors : o.concat(H.errors)), (c = o.length));
                    var d = h === c;
                    if (d && l) ((l = !1), (p = [p, 1]));
                    else {
                      d && ((l = !0), (p = 1), f !== !0 && (f = !0));
                      let r = c;
                      Me(n, {
                        instancePath: t + '/change',
                        parentData: e,
                        parentDataProperty: 'change',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? Me.errors : o.concat(Me.errors)), (c = o.length));
                      var d = r === c;
                      if (d && l) ((l = !1), (p = [p, 2]));
                      else {
                        d && ((l = !0), (p = 2), f !== !0 && (f = !0));
                        let r = c;
                        Ke(n, {
                          instancePath: t + '/change',
                          parentData: e,
                          parentDataProperty: 'change',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? Ke.errors : o.concat(Ke.errors)), (c = o.length));
                        var d = r === c;
                        d && l
                          ? ((l = !1), (p = [p, 3]))
                          : d && ((l = !0), (p = 3), f !== !0 && (f = !0));
                      }
                    }
                    if (l) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/change',
                        schemaPath: '#/properties/change/oneOf',
                        keyword: 'oneOf',
                        params: { passingSchemas: p },
                        message: 'must match exactly one schema in oneOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (qe.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (qe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((qe.errors = o), c === 0);
    }
    ((qe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isEditJdTasksRequest = $e));
    var Je = {
      type: 'string',
      enum: ['title', 'description'],
      title: 'TaskField',
    };
    function Ye(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Ye.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'title' && e !== 'description'
            ? ((Ye.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Je.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Ye.errors = null), !0)
          : ((Ye.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    Ye.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function U(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = U.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.field === void 0 && (n = 'field')) ||
            (e.value === void 0 && (n = 'value'))
          )
            return (
              (U.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'field' && n !== 'value')
                return (
                  (U.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (U.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'set_field')
                  return (
                    (U.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'set_field' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.field !== void 0) {
                  let n = s;
                  Ye(e.field, {
                    instancePath: t + '/field',
                    parentData: e,
                    parentDataProperty: 'field',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? Ye.errors : o.concat(Ye.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.value !== void 0) {
                    let n = e.value,
                      r = s,
                      c = s,
                      d = !1,
                      p = s;
                    f(n, {
                      instancePath: t + '/value',
                      parentData: e,
                      parentDataProperty: 'value',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var u = p === s;
                    d ||= u;
                    let m = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/value',
                        schemaPath: '#/properties/value/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var u = m === s;
                    if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/value',
                        schemaPath: '#/properties/value/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (U.errors = o), !1);
                    }
                    var l = r === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (U.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((U.errors = o), s === 0);
    }
    U.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function W(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = W.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.detail_id === void 0 && (n = 'detail_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (W.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'detail_id' && n !== 'text')
                return (
                  (W.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (W.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_detail')
                  return (
                    (W.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.detail_id !== void 0) {
                  let n = c;
                  s(e.detail_id, {
                    instancePath: t + '/detail_id',
                    parentData: e,
                    parentDataProperty: 'detail_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.text !== void 0) {
                    let n = c;
                    f(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (W.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((W.errors = o), c === 0);
    }
    W.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function G(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = G.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.detail_id === void 0 && (n = 'detail_id'))
          )
            return (
              (G.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'detail_id')
                return (
                  (G.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (G.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'remove_detail')
                  return (
                    (G.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'remove_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.detail_id !== void 0) {
                  let n = c;
                  s(e.detail_id, {
                    instancePath: t + '/detail_id',
                    parentData: e,
                    parentDataProperty: 'detail_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (G.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((G.errors = o), c === 0);
    }
    G.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function K(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = K.evaluated;
      (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0));
      let l = s,
        u = !1,
        d = null,
        f = s;
      U(e, {
        instancePath: t,
        parentData: n,
        parentDataProperty: r,
        rootData: i,
        dynamicAnchors: a,
      }) || ((o = o === null ? U.errors : o.concat(U.errors)), (s = o.length));
      var m = f === s;
      if (m) {
        ((u = !0), (d = 0));
        var h = !0;
      }
      let g = s;
      p(e, {
        instancePath: t,
        parentData: n,
        parentDataProperty: r,
        rootData: i,
        dynamicAnchors: a,
      }) || ((o = o === null ? p.errors : o.concat(p.errors)), (s = o.length));
      var m = g === s;
      if (m && u) ((u = !1), (d = [d, 1]));
      else {
        m && ((u = !0), (d = 1), h !== !0 && (h = !0));
        let c = s;
        W(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? W.errors : o.concat(W.errors)), (s = o.length));
        var m = c === s;
        if (m && u) ((u = !1), (d = [d, 2]));
        else {
          m && ((u = !0), (d = 2), h !== !0 && (h = !0));
          let c = s;
          G(e, {
            instancePath: t,
            parentData: n,
            parentDataProperty: r,
            rootData: i,
            dynamicAnchors: a,
          }) || ((o = o === null ? G.errors : o.concat(G.errors)), (s = o.length));
          var m = c === s;
          m && u ? ((u = !1), (d = [d, 3])) : m && ((u = !0), (d = 3), h !== !0 && (h = !0));
        }
      }
      if (u) ((s = l), o !== null && (l ? (o.length = l) : (o = null)));
      else {
        let e = {
          instancePath: t,
          schemaPath: '#/oneOf',
          keyword: 'oneOf',
          params: { passingSchemas: d },
          message: 'must match exactly one schema in oneOf',
        };
        return (o === null ? (o = [e]) : o.push(e), s++, (K.errors = o), !1);
      }
      return ((K.errors = o), (c.props = h), s === 0);
    }
    K.evaluated = {
      dynamicProps: !0,
      dynamicItems: !1,
    };
    function Xe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Xe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (Xe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'task_id' && n !== 'changes')
                return (
                  (Xe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Xe.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_task')
                  return (
                    (Xe.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length < 1)
                          return (
                            (Xe.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (K(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? K.errors : o.concat(K.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (Xe.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Xe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Xe.errors = o), c === 0);
    }
    Xe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ze(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ze.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.before_task_id === void 0 && (n = 'before_task_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (Ze.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'area_id' &&
                n !== 'before_task_id' &&
                n !== 'changes'
              )
                return (
                  (Ze.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Ze.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'move_task')
                  return (
                    (Ze.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'move_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.area_id !== void 0) {
                    let n = e.area_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/area_id',
                      parentData: e,
                      parentDataProperty: 'area_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/area_id',
                        schemaPath: '#/properties/area_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/area_id',
                        schemaPath: '#/properties/area_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Ze.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_task_id !== void 0) {
                      let n = e.before_task_id,
                        r = c,
                        l = c,
                        d = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_task_id',
                        parentData: e,
                        parentDataProperty: 'before_task_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var f = p === c;
                      d ||= f;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_task_id',
                          schemaPath: '#/properties/before_task_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = m === c;
                      if (((d ||= f), d))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_task_id',
                          schemaPath: '#/properties/before_task_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (Ze.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.changes !== void 0) {
                        let n = e.changes,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (K(n[r], {
                                  instancePath: t + '/changes/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? K.errors : o.concat(K.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (Ze.errors = [
                                {
                                  instancePath: t + '/changes',
                                  schemaPath: '#/properties/changes/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Ze.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ze.errors = o), c === 0);
    }
    Ze.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Qe(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Qe.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.detail_id === void 0 && (n = 'detail_id')) ||
            (e.before_detail_id === void 0 && (n = 'before_detail_id'))
          )
            return (
              (Qe.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'detail_id' &&
                n !== 'before_detail_id'
              )
                return (
                  (Qe.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Qe.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_detail')
                  return (
                    (Qe.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.detail_id !== void 0) {
                    let n = c;
                    s(e.detail_id, {
                      instancePath: t + '/detail_id',
                      parentData: e,
                      parentDataProperty: 'detail_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_detail_id !== void 0) {
                      let n = e.before_detail_id,
                        r = c,
                        l = c,
                        f = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_detail_id',
                        parentData: e,
                        parentDataProperty: 'before_detail_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var d = p === c;
                      f ||= d;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_detail_id',
                          schemaPath: '#/properties/before_detail_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = m === c;
                      if (((f ||= d), f))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_detail_id',
                          schemaPath: '#/properties/before_detail_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (Qe.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (Qe.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Qe.errors = o), c === 0);
    }
    Qe.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function $e(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = $e.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.change === void 0 && (n = 'change'))
          )
            return (
              ($e.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'change')
                return (
                  ($e.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.change !== void 0) {
                    let n = e.change,
                      r = c,
                      s = c,
                      l = !1,
                      p = null,
                      m = c;
                    R(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? R.errors : o.concat(R.errors)), (c = o.length));
                    var d = m === c;
                    if (d) {
                      ((l = !0), (p = 0));
                      var f = !0;
                    }
                    let h = c;
                    Xe(n, {
                      instancePath: t + '/change',
                      parentData: e,
                      parentDataProperty: 'change',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Xe.errors : o.concat(Xe.errors)), (c = o.length));
                    var d = h === c;
                    if (d && l) ((l = !1), (p = [p, 1]));
                    else {
                      d && ((l = !0), (p = 1), f !== !0 && (f = !0));
                      let r = c;
                      Ze(n, {
                        instancePath: t + '/change',
                        parentData: e,
                        parentDataProperty: 'change',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? Ze.errors : o.concat(Ze.errors)), (c = o.length));
                      var d = r === c;
                      if (d && l) ((l = !1), (p = [p, 2]));
                      else {
                        d && ((l = !0), (p = 2), f !== !0 && (f = !0));
                        let r = c;
                        Qe(n, {
                          instancePath: t + '/change',
                          parentData: e,
                          parentDataProperty: 'change',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? Qe.errors : o.concat(Qe.errors)), (c = o.length));
                        var d = r === c;
                        if (d && l) ((l = !1), (p = [p, 3]));
                        else {
                          d && ((l = !0), (p = 3), f !== !0 && (f = !0));
                          let r = c;
                          Ne(n, {
                            instancePath: t + '/change',
                            parentData: e,
                            parentDataProperty: 'change',
                            rootData: i,
                            dynamicAnchors: a,
                          }) ||
                            ((o = o === null ? Ne.errors : o.concat(Ne.errors)), (c = o.length));
                          var d = r === c;
                          d && l
                            ? ((l = !1), (p = [p, 4]))
                            : d && ((l = !0), (p = 4), f !== !0 && (f = !0));
                        }
                      }
                    }
                    if (l) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/change',
                        schemaPath: '#/properties/change/oneOf',
                        keyword: 'oneOf',
                        params: { passingSchemas: p },
                        message: 'must match exactly one schema in oneOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, ($e.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            ($e.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return (($e.errors = o), c === 0);
    }
    (($e.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isExecutionStatus = et));
    function et(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = et.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'active' &&
            e !== 'paused' &&
            e !== 'completed' &&
            e !== 'cancelled' &&
            e !== 'failed'
            ? ((et.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Se.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((et.errors = null), !0)
          : ((et.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((et.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isFieldChange = tt));
    function tt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = tt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if ((e.field === void 0 && (n = 'field')) || (e.value === void 0 && (n = 'value')))
            return (
              (tt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'field' && n !== 'value')
                return (
                  (tt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.field !== void 0) {
                let n = s;
                ce(e.field, {
                  instancePath: t + '/field',
                  parentData: e,
                  parentDataProperty: 'field',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? ce.errors : o.concat(ce.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.value !== void 0) {
                  let n = e.value,
                    r = s,
                    c = s,
                    d = !1,
                    p = s;
                  f(n, {
                    instancePath: t + '/value',
                    parentData: e,
                    parentDataProperty: 'value',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                  var u = p === s;
                  d ||= u;
                  let m = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var u = m === s;
                  if (((d ||= u), d)) ((s = c), o !== null && (c ? (o.length = c) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/value',
                      schemaPath: '#/properties/value/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (tt.errors = o), !1);
                  }
                  var l = r === s;
                } else var l = !0;
              }
            }
          }
        } else
          return (
            (tt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((tt.errors = o), s === 0);
    }
    ((tt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isHealthStatus = nt));
    function nt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = nt.evaluated;
      if (
        (o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        e && typeof e == 'object' && !Array.isArray(e))
      ) {
        let n;
        if (e.status === void 0 && (n = 'status'))
          return (
            (nt.errors = [
              {
                instancePath: t,
                schemaPath: '#/required',
                keyword: 'required',
                params: { missingProperty: n },
                message: "must have required property '" + n + "'",
              },
            ]),
            !1
          );
        for (let n in e)
          if (n !== 'status')
            return (
              (nt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/additionalProperties',
                  keyword: 'additionalProperties',
                  params: { additionalProperty: n },
                  message: 'must NOT have additional properties',
                },
              ]),
              !1
            );
        if (e.status !== void 0) {
          let n = e.status;
          if (typeof n != 'string')
            return (
              (nt.errors = [
                {
                  instancePath: t + '/status',
                  schemaPath: '#/properties/status/type',
                  keyword: 'type',
                  params: { type: 'string' },
                  message: 'must be string',
                },
              ]),
              !1
            );
          if (n !== 'ok')
            return (
              (nt.errors = [
                {
                  instancePath: t + '/status',
                  schemaPath: '#/properties/status/const',
                  keyword: 'const',
                  params: { allowedValue: 'ok' },
                  message: 'must be equal to constant',
                },
              ]),
              !1
            );
        }
      } else
        return (
          (nt.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'object' },
              message: 'must be object',
            },
          ]),
          !1
        );
      return ((nt.errors = null), !0);
    }
    ((nt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isHttpErrorDetail = rt));
    function rt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = rt.evaluated;
      if (
        (o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        e && typeof e == 'object' && !Array.isArray(e))
      ) {
        let n;
        if (e.code === void 0 && (n = 'code'))
          return (
            (rt.errors = [
              {
                instancePath: t,
                schemaPath: '#/required',
                keyword: 'required',
                params: { missingProperty: n },
                message: "must have required property '" + n + "'",
              },
            ]),
            !1
          );
        for (let n in e)
          if (n !== 'code')
            return (
              (rt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/additionalProperties',
                  keyword: 'additionalProperties',
                  params: { additionalProperty: n },
                  message: 'must NOT have additional properties',
                },
              ]),
              !1
            );
        if (e.code !== void 0 && typeof e.code != 'string')
          return (
            (rt.errors = [
              {
                instancePath: t + '/code',
                schemaPath: '#/properties/code/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1
          );
      } else
        return (
          (rt.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'object' },
              message: 'must be object',
            },
          ]),
          !1
        );
      return ((rt.errors = null), !0);
    }
    ((rt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isHttpErrorResponse = it));
    function it(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = it.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.detail === void 0 && (n = 'detail'))
            return (
              (it.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'detail')
                return (
                  (it.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            n === s &&
              e.detail !== void 0 &&
              (rt(e.detail, {
                instancePath: t + '/detail',
                parentData: e,
                parentDataProperty: 'detail',
                rootData: i,
                dynamicAnchors: a,
              }) ||
                ((o = o === null ? rt.errors : o.concat(rt.errors)), (s = o.length)));
          }
        } else
          return (
            (it.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((it.errors = o), s === 0);
    }
    ((it.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewContent = ot));
    function q(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = q.evaluated;
      if (
        (o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e != 'number' || e % 1 || isNaN(e) || !isFinite(e))
      )
        return (
          (q.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'integer' },
              message: 'must be integer',
            },
          ]),
          !1
        );
      if (typeof e == 'number' && isFinite(e)) {
        if (e > 9007199254740991 || isNaN(e))
          return (
            (q.errors = [
              {
                instancePath: t,
                schemaPath: '#/maximum',
                keyword: 'maximum',
                params: {
                  comparison: '<=',
                  limit: 9007199254740991,
                },
                message: 'must be <= 9007199254740991',
              },
            ]),
            !1
          );
        if (e < 1 || isNaN(e))
          return (
            (q.errors = [
              {
                instancePath: t,
                schemaPath: '#/minimum',
                keyword: 'minimum',
                params: {
                  comparison: '>=',
                  limit: 1,
                },
                message: 'must be >= 1',
              },
            ]),
            !1
          );
      }
      return ((q.errors = null), !0);
    }
    q.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    var at = {
      type: 'string',
      enum: ['app', 'employee', 'consultant'],
      title: 'InterviewSpeaker',
    };
    function J(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = J.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'app' && e !== 'employee' && e !== 'consultant'
            ? ((J.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: at.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((J.errors = null), !0)
          : ((J.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    J.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function ot(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ot.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.kind === void 0 && (n = 'kind')) ||
            (e.interview_sequence === void 0 && (n = 'interview_sequence')) ||
            (e.speaker === void 0 && (n = 'speaker')) ||
            (e.interview_text === void 0 && (n = 'interview_text'))
          )
            return (
              (ot.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'kind' &&
                n !== 'interview_sequence' &&
                n !== 'speaker' &&
                n !== 'interview_text'
              )
                return (
                  (ot.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.kind !== void 0) {
                let n = e.kind,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (ot.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'interview')
                  return (
                    (ot.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/const',
                        keyword: 'const',
                        params: { allowedValue: 'interview' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.interview_sequence !== void 0) {
                  let n = s;
                  q(e.interview_sequence, {
                    instancePath: t + '/interview_sequence',
                    parentData: e,
                    parentDataProperty: 'interview_sequence',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? q.errors : o.concat(q.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.speaker !== void 0) {
                    let n = s;
                    J(e.speaker, {
                      instancePath: t + '/speaker',
                      parentData: e,
                      parentDataProperty: 'speaker',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? J.errors : o.concat(J.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                  if (l) {
                    if (e.interview_text !== void 0) {
                      let n = s;
                      if (typeof e.interview_text != 'string')
                        return (
                          (ot.errors = [
                            {
                              instancePath: t + '/interview_text',
                              schemaPath: '#/properties/interview_text/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var l = n === s;
                    } else var l = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (ot.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ot.errors = o), s === 0);
    }
    ((ot.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewHistory = ct));
    function st(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = st.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.source_id === void 0 && (n = 'source_id')) ||
            (e.interview_sequence === void 0 && (n = 'interview_sequence')) ||
            (e.speaker === void 0 && (n = 'speaker')) ||
            (e.interview_text === void 0 && (n = 'interview_text')) ||
            (e.execution_id === void 0 && (n = 'execution_id'))
          )
            return (
              (st.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'source_id' &&
                n !== 'interview_sequence' &&
                n !== 'speaker' &&
                n !== 'interview_text' &&
                n !== 'execution_id'
              )
                return (
                  (st.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.source_id !== void 0) {
                let n = c;
                s(e.source_id, {
                  instancePath: t + '/source_id',
                  parentData: e,
                  parentDataProperty: 'source_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.interview_sequence !== void 0) {
                  let n = c;
                  q(e.interview_sequence, {
                    instancePath: t + '/interview_sequence',
                    parentData: e,
                    parentDataProperty: 'interview_sequence',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.speaker !== void 0) {
                    let n = c;
                    J(e.speaker, {
                      instancePath: t + '/speaker',
                      parentData: e,
                      parentDataProperty: 'speaker',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? J.errors : o.concat(J.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.interview_text !== void 0) {
                      let n = c;
                      if (typeof e.interview_text != 'string')
                        return (
                          (st.errors = [
                            {
                              instancePath: t + '/interview_text',
                              schemaPath: '#/properties/interview_text/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.execution_id !== void 0) {
                        let n = e.execution_id,
                          r = c,
                          l = c,
                          f = !1,
                          p = c;
                        s(n, {
                          instancePath: t + '/execution_id',
                          parentData: e,
                          parentDataProperty: 'execution_id',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                        var d = p === c;
                        f ||= d;
                        let m = c;
                        if (n !== null) {
                          let e = {
                            instancePath: t + '/execution_id',
                            schemaPath: '#/properties/execution_id/anyOf/1/type',
                            keyword: 'type',
                            params: { type: 'null' },
                            message: 'must be null',
                          };
                          (o === null ? (o = [e]) : o.push(e), c++);
                        }
                        var d = m === c;
                        if (((f ||= d), f))
                          ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                        else {
                          let e = {
                            instancePath: t + '/execution_id',
                            schemaPath: '#/properties/execution_id/anyOf',
                            keyword: 'anyOf',
                            params: {},
                            message: 'must match a schema in anyOf',
                          };
                          return (o === null ? (o = [e]) : o.push(e), c++, (st.errors = o), !1);
                        }
                        var u = r === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (st.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((st.errors = o), c === 0);
    }
    st.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function ct(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ct.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.messages === void 0 && (n = 'messages'))
            return (
              (ct.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'messages')
                return (
                  (ct.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s && e.messages !== void 0) {
              let n = e.messages;
              if (s === s) {
                if (Array.isArray(n)) {
                  let e = n.length;
                  for (let r = 0; r < e; r++) {
                    let e = s;
                    if (
                      (st(n[r], {
                        instancePath: t + '/messages/' + r,
                        parentData: n,
                        parentDataProperty: r,
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? st.errors : o.concat(st.errors)), (s = o.length)),
                      e !== s)
                    )
                      break;
                  }
                } else
                  return (
                    (ct.errors = [
                      {
                        instancePath: t + '/messages',
                        schemaPath: '#/properties/messages/type',
                        keyword: 'type',
                        params: { type: 'array' },
                        message: 'must be array',
                      },
                    ]),
                    !1
                  );
              }
            }
          }
        } else
          return (
            (ct.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ct.errors = o), s === 0);
    }
    ((ct.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewMessage = lt));
    function lt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = lt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.source_id === void 0 && (n = 'source_id')) ||
            (e.interview_sequence === void 0 && (n = 'interview_sequence')) ||
            (e.speaker === void 0 && (n = 'speaker')) ||
            (e.interview_text === void 0 && (n = 'interview_text')) ||
            (e.execution_id === void 0 && (n = 'execution_id'))
          )
            return (
              (lt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'source_id' &&
                n !== 'interview_sequence' &&
                n !== 'speaker' &&
                n !== 'interview_text' &&
                n !== 'execution_id'
              )
                return (
                  (lt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.source_id !== void 0) {
                let n = c;
                s(e.source_id, {
                  instancePath: t + '/source_id',
                  parentData: e,
                  parentDataProperty: 'source_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.interview_sequence !== void 0) {
                  let n = c;
                  q(e.interview_sequence, {
                    instancePath: t + '/interview_sequence',
                    parentData: e,
                    parentDataProperty: 'interview_sequence',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.speaker !== void 0) {
                    let n = c;
                    J(e.speaker, {
                      instancePath: t + '/speaker',
                      parentData: e,
                      parentDataProperty: 'speaker',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? J.errors : o.concat(J.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.interview_text !== void 0) {
                      let n = c;
                      if (typeof e.interview_text != 'string')
                        return (
                          (lt.errors = [
                            {
                              instancePath: t + '/interview_text',
                              schemaPath: '#/properties/interview_text/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.execution_id !== void 0) {
                        let n = e.execution_id,
                          r = c,
                          l = c,
                          f = !1,
                          p = c;
                        s(n, {
                          instancePath: t + '/execution_id',
                          parentData: e,
                          parentDataProperty: 'execution_id',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                        var d = p === c;
                        f ||= d;
                        let m = c;
                        if (n !== null) {
                          let e = {
                            instancePath: t + '/execution_id',
                            schemaPath: '#/properties/execution_id/anyOf/1/type',
                            keyword: 'type',
                            params: { type: 'null' },
                            message: 'must be null',
                          };
                          (o === null ? (o = [e]) : o.push(e), c++);
                        }
                        var d = m === c;
                        if (((f ||= d), f))
                          ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                        else {
                          let e = {
                            instancePath: t + '/execution_id',
                            schemaPath: '#/properties/execution_id/anyOf',
                            keyword: 'anyOf',
                            params: {},
                            message: 'must match a schema in anyOf',
                          };
                          return (o === null ? (o = [e]) : o.push(e), c++, (lt.errors = o), !1);
                        }
                        var u = r === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (lt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((lt.errors = o), c === 0);
    }
    ((lt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewPlan = ut));
    function ut(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ut.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.plan === void 0 && (n = 'plan'))
            return (
              (ut.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'plan')
                return (
                  (ut.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s && e.plan !== void 0) {
              let n = e.plan,
                r = s,
                i = !1,
                a = s;
              if (typeof n != 'string') {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf/0/type',
                  keyword: 'type',
                  params: { type: 'string' },
                  message: 'must be string',
                };
                (o === null ? (o = [e]) : o.push(e), s++);
              }
              var l = a === s;
              i ||= l;
              let c = s;
              if (n !== null) {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf/1/type',
                  keyword: 'type',
                  params: { type: 'null' },
                  message: 'must be null',
                };
                (o === null ? (o = [e]) : o.push(e), s++);
              }
              var l = c === s;
              if (((i ||= l), i)) ((s = r), o !== null && (r ? (o.length = r) : (o = null)));
              else {
                let e = {
                  instancePath: t + '/plan',
                  schemaPath: '#/properties/plan/anyOf',
                  keyword: 'anyOf',
                  params: {},
                  message: 'must match a schema in anyOf',
                };
                return (o === null ? (o = [e]) : o.push(e), s++, (ut.errors = o), !1);
              }
            }
          }
        } else
          return (
            (ut.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ut.errors = o), s === 0);
    }
    ((ut.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewPlanView = dt));
    function dt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = dt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.plan === void 0 && (n = 'plan')) ||
            (e.job_file_id === void 0 && (n = 'job_file_id'))
          )
            return (
              (dt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'plan' && n !== 'job_file_id')
                return (
                  (dt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.plan !== void 0) {
                let n = e.plan,
                  r = c,
                  i = c,
                  a = !1,
                  s = c;
                if (typeof n != 'string') {
                  let e = {
                    instancePath: t + '/plan',
                    schemaPath: '#/properties/plan/anyOf/0/type',
                    keyword: 'type',
                    params: { type: 'string' },
                    message: 'must be string',
                  };
                  (o === null ? (o = [e]) : o.push(e), c++);
                }
                var u = s === c;
                a ||= u;
                let l = c;
                if (n !== null) {
                  let e = {
                    instancePath: t + '/plan',
                    schemaPath: '#/properties/plan/anyOf/1/type',
                    keyword: 'type',
                    params: { type: 'null' },
                    message: 'must be null',
                  };
                  (o === null ? (o = [e]) : o.push(e), c++);
                }
                var u = l === c;
                if (((a ||= u), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                else {
                  let e = {
                    instancePath: t + '/plan',
                    schemaPath: '#/properties/plan/anyOf',
                    keyword: 'anyOf',
                    params: {},
                    message: 'must match a schema in anyOf',
                  };
                  return (o === null ? (o = [e]) : o.push(e), c++, (dt.errors = o), !1);
                }
                var d = r === c;
              } else var d = !0;
              if (d) {
                if (e.job_file_id !== void 0) {
                  let n = c;
                  s(e.job_file_id, {
                    instancePath: t + '/job_file_id',
                    parentData: e,
                    parentDataProperty: 'job_file_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = n === c;
                } else var d = !0;
              }
            }
          }
        } else
          return (
            (dt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((dt.errors = o), c === 0);
    }
    ((dt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isInterviewSpeaker = ft));
    function ft(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = ft.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'app' && e !== 'employee' && e !== 'consultant'
            ? ((ft.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: at.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((ft.errors = null), !0)
          : ((ft.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((ft.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdAreasView = pt));
    function pt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = pt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.areas === void 0 && (n = 'areas'))
          )
            return (
              (pt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'areas')
                return (
                  (pt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.areas !== void 0) {
                  let n = e.areas,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (g(n[r], {
                            instancePath: t + '/areas/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? g.errors : o.concat(g.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (pt.errors = [
                          {
                            instancePath: t + '/areas',
                            schemaPath: '#/properties/areas/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (pt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((pt.errors = o), c === 0);
    }
    ((pt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdCapabilitiesView = mt));
    function mt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = mt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.capabilities === void 0 && (n = 'capabilities')) ||
            (e.task_links === void 0 && (n = 'task_links'))
          )
            return (
              (mt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'capabilities' && n !== 'task_links')
                return (
                  (mt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.capabilities !== void 0) {
                  let n = e.capabilities,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (C(n[r], {
                            instancePath: t + '/capabilities/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? C.errors : o.concat(C.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (mt.errors = [
                          {
                            instancePath: t + '/capabilities',
                            schemaPath: '#/properties/capabilities/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.task_links !== void 0) {
                    let n = e.task_links,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        let e = n.length;
                        for (let r = 0; r < e; r++) {
                          let e = c;
                          if (
                            (w(n[r], {
                              instancePath: t + '/task_links/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? w.errors : o.concat(w.errors)), (c = o.length)),
                            e !== c)
                          )
                            break;
                        }
                      } else
                        return (
                          (mt.errors = [
                            {
                              instancePath: t + '/task_links',
                              schemaPath: '#/properties/task_links/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (mt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((mt.errors = o), c === 0);
    }
    ((mt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdCollaboratorsView = ht));
    function ht(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = ht.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.collaborators === void 0 && (n = 'collaborators'))
          )
            return (
              (ht.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'collaborators')
                return (
                  (ht.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.collaborators !== void 0) {
                  let n = e.collaborators,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (T(n[r], {
                            instancePath: t + '/collaborators/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? T.errors : o.concat(T.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (ht.errors = [
                          {
                            instancePath: t + '/collaborators',
                            schemaPath: '#/properties/collaborators/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (ht.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ht.errors = o), c === 0);
    }
    ((ht.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdConditionsView = gt));
    function gt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = gt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.conditions === void 0 && (n = 'conditions'))
          )
            return (
              (gt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'conditions')
                return (
                  (gt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.conditions !== void 0) {
                  let n = e.conditions,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (D(n[r], {
                            instancePath: t + '/conditions/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? D.errors : o.concat(D.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (gt.errors = [
                          {
                            instancePath: t + '/conditions',
                            schemaPath: '#/properties/conditions/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (gt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((gt.errors = o), c === 0);
    }
    ((gt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdProfileView = Y));
    function Y(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Y.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.profile === void 0 && (n = 'profile'))
          )
            return (
              (Y.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'profile')
                return (
                  (Y.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.profile !== void 0) {
                  let n = c;
                  y(e.profile, {
                    instancePath: t + '/profile',
                    parentData: e,
                    parentDataProperty: 'profile',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? y.errors : o.concat(y.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Y.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Y.errors = o), c === 0);
    }
    ((Y.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdSourceChangesView = vt));
    function _t(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = _t.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.snapshot_id === void 0 && (n = 'snapshot_id')) ||
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.covered_through_sequence === void 0 && (n = 'covered_through_sequence'))
          )
            return (
              (_t.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'snapshot_id' && n !== 'revision_id' && n !== 'covered_through_sequence')
                return (
                  (_t.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.snapshot_id !== void 0) {
                let n = c;
                s(e.snapshot_id, {
                  instancePath: t + '/snapshot_id',
                  parentData: e,
                  parentDataProperty: 'snapshot_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.revision_id !== void 0) {
                  let n = e.revision_id,
                    r = c,
                    l = c,
                    f = !1,
                    p = c;
                  s(n, {
                    instancePath: t + '/revision_id',
                    parentData: e,
                    parentDataProperty: 'revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = p === c;
                  f ||= d;
                  let m = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/revision_id',
                      schemaPath: '#/properties/revision_id/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = m === c;
                  if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/revision_id',
                      schemaPath: '#/properties/revision_id/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (_t.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.covered_through_sequence !== void 0) {
                    let n = c;
                    q(e.covered_through_sequence, {
                      instancePath: t + '/covered_through_sequence',
                      parentData: e,
                      parentDataProperty: 'covered_through_sequence',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (_t.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((_t.errors = o), c === 0);
    }
    _t.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function vt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = vt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.citation_id === void 0 && (n = 'citation_id')) ||
            (e.jd_markdown === void 0 && (n = 'jd_markdown')) ||
            (e.source_markdown === void 0 && (n = 'source_markdown')) ||
            (e.source_version === void 0 && (n = 'source_version')) ||
            (e.comparison_version === void 0 && (n = 'comparison_version'))
          )
            return (
              (vt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'revision_id' &&
                n !== 'citation_id' &&
                n !== 'jd_markdown' &&
                n !== 'source_markdown' &&
                n !== 'source_version' &&
                n !== 'comparison_version'
              )
                return (
                  (vt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.citation_id !== void 0) {
                  let n = c;
                  s(e.citation_id, {
                    instancePath: t + '/citation_id',
                    parentData: e,
                    parentDataProperty: 'citation_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.jd_markdown !== void 0) {
                    let n = c;
                    if (typeof e.jd_markdown != 'string')
                      return (
                        (vt.errors = [
                          {
                            instancePath: t + '/jd_markdown',
                            schemaPath: '#/properties/jd_markdown/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.source_markdown !== void 0) {
                      let n = e.source_markdown,
                        r = c,
                        i = c,
                        a = !1,
                        s = c;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/source_markdown',
                          schemaPath: '#/properties/source_markdown/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = s === c;
                      a ||= d;
                      let l = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/source_markdown',
                          schemaPath: '#/properties/source_markdown/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = l === c;
                      if (((a ||= d), a))
                        ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/source_markdown',
                          schemaPath: '#/properties/source_markdown/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (vt.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.source_version !== void 0) {
                        let n = e.source_version,
                          r = c,
                          s = c,
                          l = !1,
                          d = c;
                        _t(n, {
                          instancePath: t + '/source_version',
                          parentData: e,
                          parentDataProperty: 'source_version',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? _t.errors : o.concat(_t.errors)), (c = o.length));
                        var f = d === c;
                        l ||= f;
                        let p = c;
                        if (n !== null) {
                          let e = {
                            instancePath: t + '/source_version',
                            schemaPath: '#/properties/source_version/anyOf/1/type',
                            keyword: 'type',
                            params: { type: 'null' },
                            message: 'must be null',
                          };
                          (o === null ? (o = [e]) : o.push(e), c++);
                        }
                        var f = p === c;
                        if (((l ||= f), l))
                          ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                        else {
                          let e = {
                            instancePath: t + '/source_version',
                            schemaPath: '#/properties/source_version/anyOf',
                            keyword: 'anyOf',
                            params: {},
                            message: 'must match a schema in anyOf',
                          };
                          return (o === null ? (o = [e]) : o.push(e), c++, (vt.errors = o), !1);
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.comparison_version !== void 0) {
                          let n = e.comparison_version,
                            r = c,
                            s = c,
                            l = !1,
                            d = c;
                          _t(n, {
                            instancePath: t + '/comparison_version',
                            parentData: e,
                            parentDataProperty: 'comparison_version',
                            rootData: i,
                            dynamicAnchors: a,
                          }) ||
                            ((o = o === null ? _t.errors : o.concat(_t.errors)), (c = o.length));
                          var p = d === c;
                          l ||= p;
                          let f = c;
                          if (n !== null) {
                            let e = {
                              instancePath: t + '/comparison_version',
                              schemaPath: '#/properties/comparison_version/anyOf/1/type',
                              keyword: 'type',
                              params: { type: 'null' },
                              message: 'must be null',
                            };
                            (o === null ? (o = [e]) : o.push(e), c++);
                          }
                          var p = f === c;
                          if (((l ||= p), l))
                            ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                          else {
                            let e = {
                              instancePath: t + '/comparison_version',
                              schemaPath: '#/properties/comparison_version/anyOf',
                              keyword: 'anyOf',
                              params: {},
                              message: 'must match a schema in anyOf',
                            };
                            return (o === null ? (o = [e]) : o.push(e), c++, (vt.errors = o), !1);
                          }
                          var u = r === c;
                        } else var u = !0;
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (vt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((vt.errors = o), c === 0);
    }
    ((vt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdSourceContentView = Ct));
    var yt = {
        properties: {
          kind: {
            type: 'string',
            enum: ['work_situation', 'work_understanding'],
            title: 'Kind',
          },
          title: {
            type: 'string',
            title: 'Title',
          },
          description: {
            type: 'string',
            title: 'Description',
          },
          body: {
            type: 'string',
            title: 'Body',
          },
          references: {
            items: { $ref: '#/components/schemas/SourceLink' },
            type: 'array',
            title: 'References',
          },
        },
        additionalProperties: !1,
        type: 'object',
        required: ['kind', 'title', 'description', 'body', 'references'],
        title: 'MemoryContent',
      },
      bt = {
        properties: {
          source_ref: { $ref: '#/components/schemas/NonemptyText' },
          kind: {
            type: 'string',
            enum: ['interview', 'work_situation'],
            title: 'Kind',
          },
          label: {
            type: 'string',
            title: 'Label',
          },
        },
        additionalProperties: !1,
        type: 'object',
        required: ['source_ref', 'kind', 'label'],
        title: 'SourceLink',
      };
    function xt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = xt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.source_ref === void 0 && (n = 'source_ref')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.label === void 0 && (n = 'label'))
          )
            return (
              (xt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'source_ref' && n !== 'kind' && n !== 'label')
                return (
                  (xt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.source_ref !== void 0) {
                let n = s;
                M(e.source_ref, {
                  instancePath: t + '/source_ref',
                  parentData: e,
                  parentDataProperty: 'source_ref',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.kind !== void 0) {
                  let n = e.kind,
                    r = s;
                  if (typeof n != 'string')
                    return (
                      (xt.errors = [
                        {
                          instancePath: t + '/kind',
                          schemaPath: '#/properties/kind/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  if (n !== 'interview' && n !== 'work_situation')
                    return (
                      (xt.errors = [
                        {
                          instancePath: t + '/kind',
                          schemaPath: '#/properties/kind/enum',
                          keyword: 'enum',
                          params: { allowedValues: bt.properties.kind.enum },
                          message: 'must be equal to one of the allowed values',
                        },
                      ]),
                      !1
                    );
                  var l = r === s;
                } else var l = !0;
                if (l) {
                  if (e.label !== void 0) {
                    let n = s;
                    if (typeof e.label != 'string')
                      return (
                        (xt.errors = [
                          {
                            instancePath: t + '/label',
                            schemaPath: '#/properties/label/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (xt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((xt.errors = o), s === 0);
    }
    xt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function St(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = St.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.kind === void 0 && (n = 'kind')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.body === void 0 && (n = 'body')) ||
            (e.references === void 0 && (n = 'references'))
          )
            return (
              (St.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'kind' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'body' &&
                n !== 'references'
              )
                return (
                  (St.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.kind !== void 0) {
                let n = e.kind,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (St.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'work_situation' && n !== 'work_understanding')
                  return (
                    (St.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/enum',
                        keyword: 'enum',
                        params: { allowedValues: yt.properties.kind.enum },
                        message: 'must be equal to one of the allowed values',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.title !== void 0) {
                  let n = s;
                  if (typeof e.title != 'string')
                    return (
                      (St.errors = [
                        {
                          instancePath: t + '/title',
                          schemaPath: '#/properties/title/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.description !== void 0) {
                    let n = s;
                    if (typeof e.description != 'string')
                      return (
                        (St.errors = [
                          {
                            instancePath: t + '/description',
                            schemaPath: '#/properties/description/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var l = n === s;
                  } else var l = !0;
                  if (l) {
                    if (e.body !== void 0) {
                      let n = s;
                      if (typeof e.body != 'string')
                        return (
                          (St.errors = [
                            {
                              instancePath: t + '/body',
                              schemaPath: '#/properties/body/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var l = n === s;
                    } else var l = !0;
                    if (l) {
                      if (e.references !== void 0) {
                        let n = e.references,
                          r = s;
                        if (s === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = s;
                              if (
                                (xt(n[r], {
                                  instancePath: t + '/references/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? xt.errors : o.concat(xt.errors)),
                                  (s = o.length)),
                                e !== s)
                              )
                                break;
                            }
                          } else
                            return (
                              (St.errors = [
                                {
                                  instancePath: t + '/references',
                                  schemaPath: '#/properties/references/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var l = r === s;
                      } else var l = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (St.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((St.errors = o), s === 0);
    }
    St.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ct(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ct.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.citation_id === void 0 && (n = 'citation_id')) ||
            (e.content === void 0 && (n = 'content'))
          )
            return (
              (Ct.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'citation_id' && n !== 'content')
                return (
                  (Ct.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.citation_id !== void 0) {
                  let n = c;
                  s(e.citation_id, {
                    instancePath: t + '/citation_id',
                    parentData: e,
                    parentDataProperty: 'citation_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.content !== void 0) {
                    let n = e.content,
                      r = c,
                      s = c,
                      l = !1,
                      p = c;
                    St(n, {
                      instancePath: t + '/content',
                      parentData: e,
                      parentDataProperty: 'content',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? St.errors : o.concat(St.errors)), (c = o.length));
                    var d = p === c;
                    if (((l ||= d), d)) var f = !0;
                    let m = c;
                    ot(n, {
                      instancePath: t + '/content',
                      parentData: e,
                      parentDataProperty: 'content',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? ot.errors : o.concat(ot.errors)), (c = o.length));
                    var d = m === c;
                    if (((l ||= d), d && f !== !0 && (f = !0), l))
                      ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/content',
                        schemaPath: '#/properties/content/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Ct.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Ct.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ct.errors = o), c === 0);
    }
    ((Ct.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdSourcesView = Ot));
    var wt = {
        properties: {
          citation_id: { $ref: '#/components/schemas/WireUuid' },
          target_label: {
            type: 'string',
            title: 'Target Label',
          },
          target: { $ref: '#/components/schemas/Target' },
          source_kind: {
            type: 'string',
            enum: ['interview', 'work_situation', 'work_understanding'],
            title: 'Source Kind',
          },
          source_label: {
            type: 'string',
            title: 'Source Label',
          },
          needs_recheck: {
            type: 'boolean',
            title: 'Needs Recheck',
          },
          jd_changed: {
            type: 'boolean',
            title: 'Jd Changed',
          },
          source_changed: {
            type: 'boolean',
            title: 'Source Changed',
          },
        },
        additionalProperties: !1,
        type: 'object',
        required: [
          'citation_id',
          'target_label',
          'target',
          'source_kind',
          'source_label',
          'needs_recheck',
          'jd_changed',
          'source_changed',
        ],
        title: 'Reference',
      },
      Tt = {
        type: 'string',
        enum: ['profile_field', 'area', 'task', 'capability', 'collaborator', 'condition'],
        title: 'SourceTargetKind',
      };
    function Et(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Et.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'profile_field' &&
            e !== 'area' &&
            e !== 'task' &&
            e !== 'capability' &&
            e !== 'collaborator' &&
            e !== 'condition'
            ? ((Et.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Tt.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Et.errors = null), !0)
          : ((Et.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    Et.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Dt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Dt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.kind === void 0 && (n = 'kind')) ||
            (e.field === void 0 && (n = 'field')) ||
            (e.item_id === void 0 && (n = 'item_id'))
          )
            return (
              (Dt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'kind' && n !== 'field' && n !== 'item_id')
                return (
                  (Dt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.kind !== void 0) {
                let n = c;
                Et(e.kind, {
                  instancePath: t + '/kind',
                  parentData: e,
                  parentDataProperty: 'kind',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? Et.errors : o.concat(Et.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.field !== void 0) {
                  let n = e.field,
                    r = c,
                    s = c,
                    l = !1,
                    f = c;
                  k(n, {
                    instancePath: t + '/field',
                    parentData: e,
                    parentDataProperty: 'field',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? k.errors : o.concat(k.errors)), (c = o.length));
                  var d = f === c;
                  l ||= d;
                  let p = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/field',
                      schemaPath: '#/properties/field/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = p === c;
                  if (((l ||= d), l)) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/field',
                      schemaPath: '#/properties/field/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (Dt.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.item_id !== void 0) {
                    let n = e.item_id,
                      r = c,
                      l = c,
                      d = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/item_id',
                      parentData: e,
                      parentDataProperty: 'item_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var f = p === c;
                    d ||= f;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/item_id',
                        schemaPath: '#/properties/item_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = m === c;
                    if (((d ||= f), d)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/item_id',
                        schemaPath: '#/properties/item_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Dt.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Dt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Dt.errors = o), c === 0);
    }
    Dt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function X(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = X.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.citation_id === void 0 && (n = 'citation_id')) ||
            (e.target_label === void 0 && (n = 'target_label')) ||
            (e.target === void 0 && (n = 'target')) ||
            (e.source_kind === void 0 && (n = 'source_kind')) ||
            (e.source_label === void 0 && (n = 'source_label')) ||
            (e.needs_recheck === void 0 && (n = 'needs_recheck')) ||
            (e.jd_changed === void 0 && (n = 'jd_changed')) ||
            (e.source_changed === void 0 && (n = 'source_changed'))
          )
            return (
              (X.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'citation_id' &&
                n !== 'target_label' &&
                n !== 'target' &&
                n !== 'source_kind' &&
                n !== 'source_label' &&
                n !== 'needs_recheck' &&
                n !== 'jd_changed' &&
                n !== 'source_changed'
              )
                return (
                  (X.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.citation_id !== void 0) {
                let n = c;
                s(e.citation_id, {
                  instancePath: t + '/citation_id',
                  parentData: e,
                  parentDataProperty: 'citation_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.target_label !== void 0) {
                  let n = c;
                  if (typeof e.target_label != 'string')
                    return (
                      (X.errors = [
                        {
                          instancePath: t + '/target_label',
                          schemaPath: '#/properties/target_label/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.target !== void 0) {
                    let n = c;
                    Dt(e.target, {
                      instancePath: t + '/target',
                      parentData: e,
                      parentDataProperty: 'target',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Dt.errors : o.concat(Dt.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.source_kind !== void 0) {
                      let n = e.source_kind,
                        r = c;
                      if (typeof n != 'string')
                        return (
                          (X.errors = [
                            {
                              instancePath: t + '/source_kind',
                              schemaPath: '#/properties/source_kind/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      if (n !== 'interview' && n !== 'work_situation' && n !== 'work_understanding')
                        return (
                          (X.errors = [
                            {
                              instancePath: t + '/source_kind',
                              schemaPath: '#/properties/source_kind/enum',
                              keyword: 'enum',
                              params: { allowedValues: wt.properties.source_kind.enum },
                              message: 'must be equal to one of the allowed values',
                            },
                          ]),
                          !1
                        );
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.source_label !== void 0) {
                        let n = c;
                        if (typeof e.source_label != 'string')
                          return (
                            (X.errors = [
                              {
                                instancePath: t + '/source_label',
                                schemaPath: '#/properties/source_label/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              },
                            ]),
                            !1
                          );
                        var u = n === c;
                      } else var u = !0;
                      if (u) {
                        if (e.needs_recheck !== void 0) {
                          let n = c;
                          if (typeof e.needs_recheck != 'boolean')
                            return (
                              (X.errors = [
                                {
                                  instancePath: t + '/needs_recheck',
                                  schemaPath: '#/properties/needs_recheck/type',
                                  keyword: 'type',
                                  params: { type: 'boolean' },
                                  message: 'must be boolean',
                                },
                              ]),
                              !1
                            );
                          var u = n === c;
                        } else var u = !0;
                        if (u) {
                          if (e.jd_changed !== void 0) {
                            let n = c;
                            if (typeof e.jd_changed != 'boolean')
                              return (
                                (X.errors = [
                                  {
                                    instancePath: t + '/jd_changed',
                                    schemaPath: '#/properties/jd_changed/type',
                                    keyword: 'type',
                                    params: { type: 'boolean' },
                                    message: 'must be boolean',
                                  },
                                ]),
                                !1
                              );
                            var u = n === c;
                          } else var u = !0;
                          if (u) {
                            if (e.source_changed !== void 0) {
                              let n = c;
                              if (typeof e.source_changed != 'boolean')
                                return (
                                  (X.errors = [
                                    {
                                      instancePath: t + '/source_changed',
                                      schemaPath: '#/properties/source_changed/type',
                                      keyword: 'type',
                                      params: { type: 'boolean' },
                                      message: 'must be boolean',
                                    },
                                  ]),
                                  !1
                                );
                              var u = n === c;
                            } else var u = !0;
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (X.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((X.errors = o), c === 0);
    }
    X.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function Ot(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ot.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.references === void 0 && (n = 'references'))
          )
            return (
              (Ot.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'references')
                return (
                  (Ot.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.references !== void 0) {
                  let n = e.references,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (X(n[r], {
                            instancePath: t + '/references/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? X.errors : o.concat(X.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (Ot.errors = [
                          {
                            instancePath: t + '/references',
                            schemaPath: '#/properties/references/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (Ot.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ot.errors = o), c === 0);
    }
    ((Ot.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdTasksView = kt));
    function kt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = kt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.tasks === void 0 && (n = 'tasks'))
          )
            return (
              (kt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'revision_id' && n !== 'tasks')
                return (
                  (kt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.tasks !== void 0) {
                  let n = e.tasks,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (x(n[r], {
                            instancePath: t + '/tasks/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? x.errors : o.concat(x.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (kt.errors = [
                          {
                            instancePath: t + '/tasks',
                            schemaPath: '#/properties/tasks/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (kt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((kt.errors = o), c === 0);
    }
    ((kt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJdWorkView = Z));
    function Z(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Z.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.areas === void 0 && (n = 'areas')) ||
            (e.tasks === void 0 && (n = 'tasks')) ||
            (e.capabilities === void 0 && (n = 'capabilities')) ||
            (e.task_links === void 0 && (n = 'task_links')) ||
            (e.collaborators === void 0 && (n = 'collaborators')) ||
            (e.conditions === void 0 && (n = 'conditions'))
          )
            return (
              (Z.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'revision_id' &&
                n !== 'areas' &&
                n !== 'tasks' &&
                n !== 'capabilities' &&
                n !== 'task_links' &&
                n !== 'collaborators' &&
                n !== 'conditions'
              )
                return (
                  (Z.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.revision_id !== void 0) {
                let n = c;
                s(e.revision_id, {
                  instancePath: t + '/revision_id',
                  parentData: e,
                  parentDataProperty: 'revision_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.areas !== void 0) {
                  let n = e.areas,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (g(n[r], {
                            instancePath: t + '/areas/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? g.errors : o.concat(g.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (Z.errors = [
                          {
                            instancePath: t + '/areas',
                            schemaPath: '#/properties/areas/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.tasks !== void 0) {
                    let n = e.tasks,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        let e = n.length;
                        for (let r = 0; r < e; r++) {
                          let e = c;
                          if (
                            (x(n[r], {
                              instancePath: t + '/tasks/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? x.errors : o.concat(x.errors)), (c = o.length)),
                            e !== c)
                          )
                            break;
                        }
                      } else
                        return (
                          (Z.errors = [
                            {
                              instancePath: t + '/tasks',
                              schemaPath: '#/properties/tasks/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.capabilities !== void 0) {
                      let n = e.capabilities,
                        r = c;
                      if (c === r) {
                        if (Array.isArray(n)) {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (C(n[r], {
                                instancePath: t + '/capabilities/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? C.errors : o.concat(C.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        } else
                          return (
                            (Z.errors = [
                              {
                                instancePath: t + '/capabilities',
                                schemaPath: '#/properties/capabilities/type',
                                keyword: 'type',
                                params: { type: 'array' },
                                message: 'must be array',
                              },
                            ]),
                            !1
                          );
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.task_links !== void 0) {
                        let n = e.task_links,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (w(n[r], {
                                  instancePath: t + '/task_links/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? w.errors : o.concat(w.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (Z.errors = [
                                {
                                  instancePath: t + '/task_links',
                                  schemaPath: '#/properties/task_links/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.collaborators !== void 0) {
                          let n = e.collaborators,
                            r = c;
                          if (c === r) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (T(n[r], {
                                    instancePath: t + '/collaborators/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? T.errors : o.concat(T.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else
                              return (
                                (Z.errors = [
                                  {
                                    instancePath: t + '/collaborators',
                                    schemaPath: '#/properties/collaborators/type',
                                    keyword: 'type',
                                    params: { type: 'array' },
                                    message: 'must be array',
                                  },
                                ]),
                                !1
                              );
                          }
                          var u = r === c;
                        } else var u = !0;
                        if (u) {
                          if (e.conditions !== void 0) {
                            let n = e.conditions,
                              r = c;
                            if (c === r) {
                              if (Array.isArray(n)) {
                                let e = n.length;
                                for (let r = 0; r < e; r++) {
                                  let e = c;
                                  if (
                                    (D(n[r], {
                                      instancePath: t + '/conditions/' + r,
                                      parentData: n,
                                      parentDataProperty: r,
                                      rootData: i,
                                      dynamicAnchors: a,
                                    }) ||
                                      ((o = o === null ? D.errors : o.concat(D.errors)),
                                      (c = o.length)),
                                    e !== c)
                                  )
                                    break;
                                }
                              } else
                                return (
                                  (Z.errors = [
                                    {
                                      instancePath: t + '/conditions',
                                      schemaPath: '#/properties/conditions/type',
                                      keyword: 'type',
                                      params: { type: 'array' },
                                      message: 'must be array',
                                    },
                                  ]),
                                  !1
                                );
                            }
                            var u = r === c;
                          } else var u = !0;
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Z.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Z.errors = o), c === 0);
    }
    ((Z.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJobFile = Q));
    var At = i().fullFormats['date-time'];
    function Q(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Q.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_file_id === void 0 && (n = 'job_file_id')) ||
            (e.display_name === void 0 && (n = 'display_name')) ||
            (e.name_revision === void 0 && (n = 'name_revision')) ||
            (e.employee_name === void 0 && (n = 'employee_name')) ||
            (e.created_at === void 0 && (n = 'created_at'))
          )
            return (
              (Q.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'job_file_id' &&
                n !== 'display_name' &&
                n !== 'name_revision' &&
                n !== 'employee_name' &&
                n !== 'created_at'
              )
                return (
                  (Q.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.job_file_id !== void 0) {
                let n = c;
                s(e.job_file_id, {
                  instancePath: t + '/job_file_id',
                  parentData: e,
                  parentDataProperty: 'job_file_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.display_name !== void 0) {
                  let n = c;
                  if (typeof e.display_name != 'string')
                    return (
                      (Q.errors = [
                        {
                          instancePath: t + '/display_name',
                          schemaPath: '#/properties/display_name/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.name_revision !== void 0) {
                    let n = c;
                    q(e.name_revision, {
                      instancePath: t + '/name_revision',
                      parentData: e,
                      parentDataProperty: 'name_revision',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.employee_name !== void 0) {
                      let n = c;
                      if (typeof e.employee_name != 'string')
                        return (
                          (Q.errors = [
                            {
                              instancePath: t + '/employee_name',
                              schemaPath: '#/properties/employee_name/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.created_at !== void 0) {
                        let n = e.created_at,
                          r = c;
                        if (c === r && c === r) {
                          if (typeof n == 'string') {
                            if (!At.validate(n))
                              return (
                                (Q.errors = [
                                  {
                                    instancePath: t + '/created_at',
                                    schemaPath: '#/properties/created_at/format',
                                    keyword: 'format',
                                    params: { format: 'date-time' },
                                    message: 'must match format "date-time"',
                                  },
                                ]),
                                !1
                              );
                          } else
                            return (
                              (Q.errors = [
                                {
                                  instancePath: t + '/created_at',
                                  schemaPath: '#/properties/created_at/type',
                                  keyword: 'type',
                                  params: { type: 'string' },
                                  message: 'must be string',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Q.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Q.errors = o), c === 0);
    }
    ((Q.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isJobFileList = jt));
    function jt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = jt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (e.job_files === void 0 && (n = 'job_files'))
            return (
              (jt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'job_files')
                return (
                  (jt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s && e.job_files !== void 0) {
              let n = e.job_files;
              if (s === s) {
                if (Array.isArray(n)) {
                  let e = n.length;
                  for (let r = 0; r < e; r++) {
                    let e = s;
                    if (
                      (Q(n[r], {
                        instancePath: t + '/job_files/' + r,
                        parentData: n,
                        parentDataProperty: r,
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? Q.errors : o.concat(Q.errors)), (s = o.length)),
                      e !== s)
                    )
                      break;
                  }
                } else
                  return (
                    (jt.errors = [
                      {
                        instancePath: t + '/job_files',
                        schemaPath: '#/properties/job_files/type',
                        keyword: 'type',
                        params: { type: 'array' },
                        message: 'must be array',
                      },
                    ]),
                    !1
                  );
              }
            }
          }
        } else
          return (
            (jt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((jt.errors = o), s === 0);
    }
    ((jt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isMemoryContent = Mt));
    function Mt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Mt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.kind === void 0 && (n = 'kind')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.body === void 0 && (n = 'body')) ||
            (e.references === void 0 && (n = 'references'))
          )
            return (
              (Mt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'kind' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'body' &&
                n !== 'references'
              )
                return (
                  (Mt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.kind !== void 0) {
                let n = e.kind,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (Mt.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'work_situation' && n !== 'work_understanding')
                  return (
                    (Mt.errors = [
                      {
                        instancePath: t + '/kind',
                        schemaPath: '#/properties/kind/enum',
                        keyword: 'enum',
                        params: { allowedValues: yt.properties.kind.enum },
                        message: 'must be equal to one of the allowed values',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.title !== void 0) {
                  let n = s;
                  if (typeof e.title != 'string')
                    return (
                      (Mt.errors = [
                        {
                          instancePath: t + '/title',
                          schemaPath: '#/properties/title/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.description !== void 0) {
                    let n = s;
                    if (typeof e.description != 'string')
                      return (
                        (Mt.errors = [
                          {
                            instancePath: t + '/description',
                            schemaPath: '#/properties/description/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var l = n === s;
                  } else var l = !0;
                  if (l) {
                    if (e.body !== void 0) {
                      let n = s;
                      if (typeof e.body != 'string')
                        return (
                          (Mt.errors = [
                            {
                              instancePath: t + '/body',
                              schemaPath: '#/properties/body/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var l = n === s;
                    } else var l = !0;
                    if (l) {
                      if (e.references !== void 0) {
                        let n = e.references,
                          r = s;
                        if (s === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = s;
                              if (
                                (xt(n[r], {
                                  instancePath: t + '/references/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? xt.errors : o.concat(xt.errors)),
                                  (s = o.length)),
                                e !== s)
                              )
                                break;
                            }
                          } else
                            return (
                              (Mt.errors = [
                                {
                                  instancePath: t + '/references',
                                  schemaPath: '#/properties/references/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var l = r === s;
                      } else var l = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Mt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Mt.errors = o), s === 0);
    }
    ((Mt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isMemoryLayer = Pt));
    var Nt = {
      type: 'string',
      enum: ['work_situation', 'work_understanding'],
      title: 'MemoryLayer',
    };
    function Pt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Pt.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'work_situation' && e !== 'work_understanding'
            ? ((Pt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Nt.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Pt.errors = null), !0)
          : ((Pt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((Pt.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isMemoryMapItem = Ft));
    function Ft(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ft.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.object_id === void 0 && (n = 'object_id')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description'))
          )
            return (
              (Ft.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'object_id' && n !== 'title' && n !== 'description')
                return (
                  (Ft.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.object_id !== void 0) {
                let n = c;
                s(e.object_id, {
                  instancePath: t + '/object_id',
                  parentData: e,
                  parentDataProperty: 'object_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.title !== void 0) {
                  let n = c;
                  if (typeof e.title != 'string')
                    return (
                      (Ft.errors = [
                        {
                          instancePath: t + '/title',
                          schemaPath: '#/properties/title/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.description !== void 0) {
                    let n = c;
                    if (typeof e.description != 'string')
                      return (
                        (Ft.errors = [
                          {
                            instancePath: t + '/description',
                            schemaPath: '#/properties/description/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Ft.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ft.errors = o), c === 0);
    }
    ((Ft.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isMoveTask = It));
    function It(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = It.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.before_task_id === void 0 && (n = 'before_task_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (It.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'area_id' &&
                n !== 'before_task_id' &&
                n !== 'changes'
              )
                return (
                  (It.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (It.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'move_task')
                  return (
                    (It.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'move_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.area_id !== void 0) {
                    let n = e.area_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/area_id',
                      parentData: e,
                      parentDataProperty: 'area_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/area_id',
                        schemaPath: '#/properties/area_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/area_id',
                        schemaPath: '#/properties/area_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (It.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_task_id !== void 0) {
                      let n = e.before_task_id,
                        r = c,
                        l = c,
                        d = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_task_id',
                        parentData: e,
                        parentDataProperty: 'before_task_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var f = p === c;
                      d ||= f;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_task_id',
                          schemaPath: '#/properties/before_task_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var f = m === c;
                      if (((d ||= f), d))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_task_id',
                          schemaPath: '#/properties/before_task_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (It.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.changes !== void 0) {
                        let n = e.changes,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (K(n[r], {
                                  instancePath: t + '/changes/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? K.errors : o.concat(K.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (It.errors = [
                                {
                                  instancePath: t + '/changes',
                                  schemaPath: '#/properties/changes/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (It.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((It.errors = o), c === 0);
    }
    ((It.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isNonblankText = Lt));
    function Lt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = Lt.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) < 1)
          return (
            (Lt.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
        if (!d.test(e))
          return (
            (Lt.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$',
                },
                message:
                  'must match pattern "^[^\\u0000]*[^\\u0000\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000][^\\u0000]*$"',
              },
            ]),
            !1
          );
      } else
        return (
          (Lt.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((Lt.errors = null), !0);
    }
    ((Lt.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isNonemptyText = Rt));
    function Rt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: o = {},
      } = {},
    ) {
      let s = Rt.evaluated;
      if (
        (s.dynamicProps && (s.props = void 0),
        s.dynamicItems && (s.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) < 1)
          return (
            (Rt.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 1 },
                message: 'must NOT have fewer than 1 characters',
              },
            ]),
            !1
          );
      } else
        return (
          (Rt.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((Rt.errors = null), !0);
    }
    ((Rt.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isNonnegativeInteger = $));
    function $(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = $.evaluated;
      if (
        (o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e != 'number' || e % 1 || isNaN(e) || !isFinite(e))
      )
        return (
          ($.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'integer' },
              message: 'must be integer',
            },
          ]),
          !1
        );
      if (typeof e == 'number' && isFinite(e)) {
        if (e > 9007199254740991 || isNaN(e))
          return (
            ($.errors = [
              {
                instancePath: t,
                schemaPath: '#/maximum',
                keyword: 'maximum',
                params: {
                  comparison: '<=',
                  limit: 9007199254740991,
                },
                message: 'must be <= 9007199254740991',
              },
            ]),
            !1
          );
        if (e < 0 || isNaN(e))
          return (
            ($.errors = [
              {
                instancePath: t,
                schemaPath: '#/minimum',
                keyword: 'minimum',
                params: {
                  comparison: '>=',
                  limit: 0,
                },
                message: 'must be >= 0',
              },
            ]),
            !1
          );
      }
      return (($.errors = null), !0);
    }
    (($.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isPositiveInteger = zt));
    function zt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = zt.evaluated;
      if (
        (o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e != 'number' || e % 1 || isNaN(e) || !isFinite(e))
      )
        return (
          (zt.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'integer' },
              message: 'must be integer',
            },
          ]),
          !1
        );
      if (typeof e == 'number' && isFinite(e)) {
        if (e > 9007199254740991 || isNaN(e))
          return (
            (zt.errors = [
              {
                instancePath: t,
                schemaPath: '#/maximum',
                keyword: 'maximum',
                params: {
                  comparison: '<=',
                  limit: 9007199254740991,
                },
                message: 'must be <= 9007199254740991',
              },
            ]),
            !1
          );
        if (e < 1 || isNaN(e))
          return (
            (zt.errors = [
              {
                instancePath: t,
                schemaPath: '#/minimum',
                keyword: 'minimum',
                params: {
                  comparison: '>=',
                  limit: 1,
                },
                message: 'must be >= 1',
              },
            ]),
            !1
          );
      }
      return ((zt.errors = null), !0);
    }
    ((zt.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isProfile = Bt));
    function Bt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Bt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.job_title === void 0 && (n = 'job_title')) ||
            (e.organization_unit === void 0 && (n = 'organization_unit')) ||
            (e.reports_to === void 0 && (n = 'reports_to')) ||
            (e.purpose === void 0 && (n = 'purpose'))
          )
            return (
              (Bt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'job_title' &&
                n !== 'organization_unit' &&
                n !== 'reports_to' &&
                n !== 'purpose'
              )
                return (
                  (Bt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.job_title !== void 0) {
                let n = e.job_title,
                  r = s,
                  i = s,
                  a = !1,
                  c = s;
                if (typeof n != 'string') {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf/0/type',
                    keyword: 'type',
                    params: { type: 'string' },
                    message: 'must be string',
                  };
                  (o === null ? (o = [e]) : o.push(e), s++);
                }
                var l = c === s;
                a ||= l;
                let d = s;
                if (n !== null) {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf/1/type',
                    keyword: 'type',
                    params: { type: 'null' },
                    message: 'must be null',
                  };
                  (o === null ? (o = [e]) : o.push(e), s++);
                }
                var l = d === s;
                if (((a ||= l), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                else {
                  let e = {
                    instancePath: t + '/job_title',
                    schemaPath: '#/properties/job_title/anyOf',
                    keyword: 'anyOf',
                    params: {},
                    message: 'must match a schema in anyOf',
                  };
                  return (o === null ? (o = [e]) : o.push(e), s++, (Bt.errors = o), !1);
                }
                var u = r === s;
              } else var u = !0;
              if (u) {
                if (e.organization_unit !== void 0) {
                  let n = e.organization_unit,
                    r = s,
                    i = s,
                    a = !1,
                    c = s;
                  if (typeof n != 'string') {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf/0/type',
                      keyword: 'type',
                      params: { type: 'string' },
                      message: 'must be string',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var d = c === s;
                  a ||= d;
                  let l = s;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), s++);
                  }
                  var d = l === s;
                  if (((a ||= d), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/organization_unit',
                      schemaPath: '#/properties/organization_unit/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), s++, (Bt.errors = o), !1);
                  }
                  var u = r === s;
                } else var u = !0;
                if (u) {
                  if (e.reports_to !== void 0) {
                    let n = e.reports_to,
                      r = s,
                      i = s,
                      a = !1,
                      c = s;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var f = c === s;
                    a ||= f;
                    let l = s;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), s++);
                    }
                    var f = l === s;
                    if (((a ||= f), a)) ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/reports_to',
                        schemaPath: '#/properties/reports_to/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), s++, (Bt.errors = o), !1);
                    }
                    var u = r === s;
                  } else var u = !0;
                  if (u) {
                    if (e.purpose !== void 0) {
                      let n = e.purpose,
                        r = s,
                        i = s,
                        a = !1,
                        c = s;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), s++);
                      }
                      var p = c === s;
                      a ||= p;
                      let l = s;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), s++);
                      }
                      var p = l === s;
                      if (((a ||= p), a))
                        ((s = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/purpose',
                          schemaPath: '#/properties/purpose/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), s++, (Bt.errors = o), !1);
                      }
                      var u = r === s;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (Bt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Bt.errors = o), s === 0);
    }
    ((Bt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isProfileField = Vt));
    function Vt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = Vt.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'job_title' && e !== 'organization_unit' && e !== 'reports_to' && e !== 'purpose'
            ? ((Vt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: ue.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((Vt.errors = null), !0)
          : ((Vt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((Vt.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isPublicCommentary = Ht));
    function Ht(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Ht.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.response_id === void 0 && (n = 'response_id')) ||
            (e.message_id === void 0 && (n = 'message_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (Ht.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'response_id' && n !== 'message_id' && n !== 'text')
                return (
                  (Ht.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.response_id !== void 0) {
                let n = s;
                M(e.response_id, {
                  instancePath: t + '/response_id',
                  parentData: e,
                  parentDataProperty: 'response_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.message_id !== void 0) {
                  let n = s;
                  M(e.message_id, {
                    instancePath: t + '/message_id',
                    parentData: e,
                    parentDataProperty: 'message_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.text !== void 0) {
                    let n = s;
                    M(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (Ht.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ht.errors = o), s === 0);
    }
    ((Ht.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isPublishedMemory = Ut));
    function Ut(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Ut.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.snapshot_id === void 0 && (n = 'snapshot_id')) ||
            (e.covered_through_sequence === void 0 && (n = 'covered_through_sequence')) ||
            (e.work_situations === void 0 && (n = 'work_situations')) ||
            (e.work_understandings === void 0 && (n = 'work_understandings'))
          )
            return (
              (Ut.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'snapshot_id' &&
                n !== 'covered_through_sequence' &&
                n !== 'work_situations' &&
                n !== 'work_understandings'
              )
                return (
                  (Ut.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.snapshot_id !== void 0) {
                let n = e.snapshot_id,
                  r = c,
                  l = c,
                  f = !1,
                  p = c;
                s(n, {
                  instancePath: t + '/snapshot_id',
                  parentData: e,
                  parentDataProperty: 'snapshot_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = p === c;
                f ||= u;
                let m = c;
                if (n !== null) {
                  let e = {
                    instancePath: t + '/snapshot_id',
                    schemaPath: '#/properties/snapshot_id/anyOf/1/type',
                    keyword: 'type',
                    params: { type: 'null' },
                    message: 'must be null',
                  };
                  (o === null ? (o = [e]) : o.push(e), c++);
                }
                var u = m === c;
                if (((f ||= u), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                else {
                  let e = {
                    instancePath: t + '/snapshot_id',
                    schemaPath: '#/properties/snapshot_id/anyOf',
                    keyword: 'anyOf',
                    params: {},
                    message: 'must match a schema in anyOf',
                  };
                  return (o === null ? (o = [e]) : o.push(e), c++, (Ut.errors = o), !1);
                }
                var d = r === c;
              } else var d = !0;
              if (d) {
                if (e.covered_through_sequence !== void 0) {
                  let n = c;
                  $(e.covered_through_sequence, {
                    instancePath: t + '/covered_through_sequence',
                    parentData: e,
                    parentDataProperty: 'covered_through_sequence',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? $.errors : o.concat($.errors)), (c = o.length));
                  var d = n === c;
                } else var d = !0;
                if (d) {
                  if (e.work_situations !== void 0) {
                    let n = e.work_situations,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        let e = n.length;
                        for (let r = 0; r < e; r++) {
                          let e = c;
                          if (
                            (Ft(n[r], {
                              instancePath: t + '/work_situations/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? Ft.errors : o.concat(Ft.errors)), (c = o.length)),
                            e !== c)
                          )
                            break;
                        }
                      } else
                        return (
                          (Ut.errors = [
                            {
                              instancePath: t + '/work_situations',
                              schemaPath: '#/properties/work_situations/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var d = r === c;
                  } else var d = !0;
                  if (d) {
                    if (e.work_understandings !== void 0) {
                      let n = e.work_understandings,
                        r = c;
                      if (c === r) {
                        if (Array.isArray(n)) {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (Ft(n[r], {
                                instancePath: t + '/work_understandings/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? Ft.errors : o.concat(Ft.errors)),
                                (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        } else
                          return (
                            (Ut.errors = [
                              {
                                instancePath: t + '/work_understandings',
                                schemaPath: '#/properties/work_understandings/type',
                                keyword: 'type',
                                params: { type: 'array' },
                                message: 'must be array',
                              },
                            ]),
                            !1
                          );
                      }
                      var d = r === c;
                    } else var d = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (Ut.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Ut.errors = o), c === 0);
    }
    ((Ut.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isPublishedMemoryObject = Wt));
    function Wt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Wt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.snapshot_id === void 0 && (n = 'snapshot_id')) ||
            (e.object_id === void 0 && (n = 'object_id')) ||
            (e.layer === void 0 && (n = 'layer')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.body === void 0 && (n = 'body'))
          )
            return (
              (Wt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'snapshot_id' &&
                n !== 'object_id' &&
                n !== 'layer' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'body'
              )
                return (
                  (Wt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.snapshot_id !== void 0) {
                let n = c;
                s(e.snapshot_id, {
                  instancePath: t + '/snapshot_id',
                  parentData: e,
                  parentDataProperty: 'snapshot_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.object_id !== void 0) {
                  let n = c;
                  s(e.object_id, {
                    instancePath: t + '/object_id',
                    parentData: e,
                    parentDataProperty: 'object_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.layer !== void 0) {
                    let n = c;
                    Pt(e.layer, {
                      instancePath: t + '/layer',
                      parentData: e,
                      parentDataProperty: 'layer',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Pt.errors : o.concat(Pt.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.title !== void 0) {
                      let n = c;
                      if (typeof e.title != 'string')
                        return (
                          (Wt.errors = [
                            {
                              instancePath: t + '/title',
                              schemaPath: '#/properties/title/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                    if (u) {
                      if (e.description !== void 0) {
                        let n = c;
                        if (typeof e.description != 'string')
                          return (
                            (Wt.errors = [
                              {
                                instancePath: t + '/description',
                                schemaPath: '#/properties/description/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              },
                            ]),
                            !1
                          );
                        var u = n === c;
                      } else var u = !0;
                      if (u) {
                        if (e.body !== void 0) {
                          let n = c;
                          if (typeof e.body != 'string')
                            return (
                              (Wt.errors = [
                                {
                                  instancePath: t + '/body',
                                  schemaPath: '#/properties/body/type',
                                  keyword: 'type',
                                  params: { type: 'string' },
                                  message: 'must be string',
                                },
                              ]),
                              !1
                            );
                          var u = n === c;
                        } else var u = !0;
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Wt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Wt.errors = o), c === 0);
    }
    ((Wt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReasoningSummary = Gt));
    function Gt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Gt.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.response_id === void 0 && (n = 'response_id')) ||
            (e.item_id === void 0 && (n = 'item_id')) ||
            (e.output_index === void 0 && (n = 'output_index')) ||
            (e.summary_index === void 0 && (n = 'summary_index')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (Gt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (
                n !== 'response_id' &&
                n !== 'item_id' &&
                n !== 'output_index' &&
                n !== 'summary_index' &&
                n !== 'text'
              )
                return (
                  (Gt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.response_id !== void 0) {
                let n = s;
                M(e.response_id, {
                  instancePath: t + '/response_id',
                  parentData: e,
                  parentDataProperty: 'response_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.item_id !== void 0) {
                  let n = s;
                  M(e.item_id, {
                    instancePath: t + '/item_id',
                    parentData: e,
                    parentDataProperty: 'item_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.output_index !== void 0) {
                    let n = s;
                    $(e.output_index, {
                      instancePath: t + '/output_index',
                      parentData: e,
                      parentDataProperty: 'output_index',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? $.errors : o.concat($.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                  if (l) {
                    if (e.summary_index !== void 0) {
                      let n = s;
                      $(e.summary_index, {
                        instancePath: t + '/summary_index',
                        parentData: e,
                        parentDataProperty: 'summary_index',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? $.errors : o.concat($.errors)), (s = o.length));
                      var l = n === s;
                    } else var l = !0;
                    if (l) {
                      if (e.text !== void 0) {
                        let n = s;
                        M(e.text, {
                          instancePath: t + '/text',
                          parentData: e,
                          parentDataProperty: 'text',
                          rootData: i,
                          dynamicAnchors: a,
                        }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                        var l = n === s;
                      } else var l = !0;
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Gt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Gt.errors = o), s === 0);
    }
    ((Gt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReference = Kt));
    function Kt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Kt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.citation_id === void 0 && (n = 'citation_id')) ||
            (e.target_label === void 0 && (n = 'target_label')) ||
            (e.target === void 0 && (n = 'target')) ||
            (e.source_kind === void 0 && (n = 'source_kind')) ||
            (e.source_label === void 0 && (n = 'source_label')) ||
            (e.needs_recheck === void 0 && (n = 'needs_recheck')) ||
            (e.jd_changed === void 0 && (n = 'jd_changed')) ||
            (e.source_changed === void 0 && (n = 'source_changed'))
          )
            return (
              (Kt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'citation_id' &&
                n !== 'target_label' &&
                n !== 'target' &&
                n !== 'source_kind' &&
                n !== 'source_label' &&
                n !== 'needs_recheck' &&
                n !== 'jd_changed' &&
                n !== 'source_changed'
              )
                return (
                  (Kt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.citation_id !== void 0) {
                let n = c;
                s(e.citation_id, {
                  instancePath: t + '/citation_id',
                  parentData: e,
                  parentDataProperty: 'citation_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.target_label !== void 0) {
                  let n = c;
                  if (typeof e.target_label != 'string')
                    return (
                      (Kt.errors = [
                        {
                          instancePath: t + '/target_label',
                          schemaPath: '#/properties/target_label/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.target !== void 0) {
                    let n = c;
                    Dt(e.target, {
                      instancePath: t + '/target',
                      parentData: e,
                      parentDataProperty: 'target',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? Dt.errors : o.concat(Dt.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.source_kind !== void 0) {
                      let n = e.source_kind,
                        r = c;
                      if (typeof n != 'string')
                        return (
                          (Kt.errors = [
                            {
                              instancePath: t + '/source_kind',
                              schemaPath: '#/properties/source_kind/type',
                              keyword: 'type',
                              params: { type: 'string' },
                              message: 'must be string',
                            },
                          ]),
                          !1
                        );
                      if (n !== 'interview' && n !== 'work_situation' && n !== 'work_understanding')
                        return (
                          (Kt.errors = [
                            {
                              instancePath: t + '/source_kind',
                              schemaPath: '#/properties/source_kind/enum',
                              keyword: 'enum',
                              params: { allowedValues: wt.properties.source_kind.enum },
                              message: 'must be equal to one of the allowed values',
                            },
                          ]),
                          !1
                        );
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.source_label !== void 0) {
                        let n = c;
                        if (typeof e.source_label != 'string')
                          return (
                            (Kt.errors = [
                              {
                                instancePath: t + '/source_label',
                                schemaPath: '#/properties/source_label/type',
                                keyword: 'type',
                                params: { type: 'string' },
                                message: 'must be string',
                              },
                            ]),
                            !1
                          );
                        var u = n === c;
                      } else var u = !0;
                      if (u) {
                        if (e.needs_recheck !== void 0) {
                          let n = c;
                          if (typeof e.needs_recheck != 'boolean')
                            return (
                              (Kt.errors = [
                                {
                                  instancePath: t + '/needs_recheck',
                                  schemaPath: '#/properties/needs_recheck/type',
                                  keyword: 'type',
                                  params: { type: 'boolean' },
                                  message: 'must be boolean',
                                },
                              ]),
                              !1
                            );
                          var u = n === c;
                        } else var u = !0;
                        if (u) {
                          if (e.jd_changed !== void 0) {
                            let n = c;
                            if (typeof e.jd_changed != 'boolean')
                              return (
                                (Kt.errors = [
                                  {
                                    instancePath: t + '/jd_changed',
                                    schemaPath: '#/properties/jd_changed/type',
                                    keyword: 'type',
                                    params: { type: 'boolean' },
                                    message: 'must be boolean',
                                  },
                                ]),
                                !1
                              );
                            var u = n === c;
                          } else var u = !0;
                          if (u) {
                            if (e.source_changed !== void 0) {
                              let n = c;
                              if (typeof e.source_changed != 'boolean')
                                return (
                                  (Kt.errors = [
                                    {
                                      instancePath: t + '/source_changed',
                                      schemaPath: '#/properties/source_changed/type',
                                      keyword: 'type',
                                      params: { type: 'boolean' },
                                      message: 'must be boolean',
                                    },
                                  ]),
                                  !1
                                );
                              var u = n === c;
                            } else var u = !0;
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Kt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Kt.errors = o), c === 0);
    }
    ((Kt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isRemoveDetail = qt));
    function qt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = qt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.detail_id === void 0 && (n = 'detail_id'))
          )
            return (
              (qt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'detail_id')
                return (
                  (qt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (qt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'remove_detail')
                  return (
                    (qt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'remove_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.detail_id !== void 0) {
                  let n = c;
                  s(e.detail_id, {
                    instancePath: t + '/detail_id',
                    parentData: e,
                    parentDataProperty: 'detail_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (qt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((qt.errors = o), c === 0);
    }
    ((qt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isRenameJobFileRequest = Jt));
    function Jt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Jt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_name_revision === void 0 && (n = 'expected_name_revision')) ||
            (e.display_name === void 0 && (n = 'display_name'))
          )
            return (
              (Jt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_name_revision' && n !== 'display_name')
                return (
                  (Jt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_name_revision !== void 0) {
                  let n = c;
                  q(e.expected_name_revision, {
                    instancePath: t + '/expected_name_revision',
                    parentData: e,
                    parentDataProperty: 'expected_name_revision',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.display_name !== void 0) {
                    let n = c;
                    L(e.display_name, {
                      instancePath: t + '/display_name',
                      parentData: e,
                      parentDataProperty: 'display_name',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? L.errors : o.concat(L.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Jt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Jt.errors = o), c === 0);
    }
    ((Jt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderArea = Yt));
    function Yt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Yt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.before_area_id === void 0 && (n = 'before_area_id'))
          )
            return (
              (Yt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'area_id' && n !== 'before_area_id')
                return (
                  (Yt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Yt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_area')
                  return (
                    (Yt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = c;
                  s(e.area_id, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_area_id !== void 0) {
                    let n = e.before_area_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_area_id',
                      parentData: e,
                      parentDataProperty: 'before_area_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_area_id',
                        schemaPath: '#/properties/before_area_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_area_id',
                        schemaPath: '#/properties/before_area_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Yt.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Yt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Yt.errors = o), c === 0);
    }
    ((Yt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderCapability = Xt));
    function Xt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Xt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.before_capability_id === void 0 && (n = 'before_capability_id'))
          )
            return (
              (Xt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'capability_id' && n !== 'before_capability_id')
                return (
                  (Xt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Xt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_capability')
                  return (
                    (Xt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_capability_id !== void 0) {
                    let n = e.before_capability_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_capability_id',
                      parentData: e,
                      parentDataProperty: 'before_capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_capability_id',
                        schemaPath: '#/properties/before_capability_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_capability_id',
                        schemaPath: '#/properties/before_capability_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Xt.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Xt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Xt.errors = o), c === 0);
    }
    ((Xt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderCollaborator = Zt));
    function Zt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Zt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.before_collaborator_id === void 0 && (n = 'before_collaborator_id'))
          )
            return (
              (Zt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'collaborator_id' && n !== 'before_collaborator_id')
                return (
                  (Zt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Zt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_collaborator')
                  return (
                    (Zt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.collaborator_id !== void 0) {
                  let n = c;
                  s(e.collaborator_id, {
                    instancePath: t + '/collaborator_id',
                    parentData: e,
                    parentDataProperty: 'collaborator_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_collaborator_id !== void 0) {
                    let n = e.before_collaborator_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_collaborator_id',
                      parentData: e,
                      parentDataProperty: 'before_collaborator_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_collaborator_id',
                        schemaPath: '#/properties/before_collaborator_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_collaborator_id',
                        schemaPath: '#/properties/before_collaborator_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Zt.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Zt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Zt.errors = o), c === 0);
    }
    ((Zt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderCondition = Qt));
    function Qt(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Qt.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.before_condition_id === void 0 && (n = 'before_condition_id'))
          )
            return (
              (Qt.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'condition_id' && n !== 'before_condition_id')
                return (
                  (Qt.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (Qt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_condition')
                  return (
                    (Qt.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.condition_id !== void 0) {
                  let n = c;
                  s(e.condition_id, {
                    instancePath: t + '/condition_id',
                    parentData: e,
                    parentDataProperty: 'condition_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.before_condition_id !== void 0) {
                    let n = e.before_condition_id,
                      r = c,
                      l = c,
                      f = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/before_condition_id',
                      parentData: e,
                      parentDataProperty: 'before_condition_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var d = p === c;
                    f ||= d;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/before_condition_id',
                        schemaPath: '#/properties/before_condition_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var d = m === c;
                    if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/before_condition_id',
                        schemaPath: '#/properties/before_condition_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Qt.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (Qt.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Qt.errors = o), c === 0);
    }
    ((Qt.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderDetail = $t));
    function $t(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = $t.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.detail_id === void 0 && (n = 'detail_id')) ||
            (e.before_detail_id === void 0 && (n = 'before_detail_id'))
          )
            return (
              ($t.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'detail_id' &&
                n !== 'before_detail_id'
              )
                return (
                  ($t.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    ($t.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_detail')
                  return (
                    ($t.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.detail_id !== void 0) {
                    let n = c;
                    s(e.detail_id, {
                      instancePath: t + '/detail_id',
                      parentData: e,
                      parentDataProperty: 'detail_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_detail_id !== void 0) {
                      let n = e.before_detail_id,
                        r = c,
                        l = c,
                        f = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_detail_id',
                        parentData: e,
                        parentDataProperty: 'before_detail_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var d = p === c;
                      f ||= d;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_detail_id',
                          schemaPath: '#/properties/before_detail_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = m === c;
                      if (((f ||= d), f))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_detail_id',
                          schemaPath: '#/properties/before_detail_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, ($t.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            ($t.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return (($t.errors = o), c === 0);
    }
    (($t.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReorderTaskCapability = en));
    function en(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = en.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.before_capability_id === void 0 && (n = 'before_capability_id'))
          )
            return (
              (en.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'action' &&
                n !== 'task_id' &&
                n !== 'capability_id' &&
                n !== 'before_capability_id'
              )
                return (
                  (en.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (en.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'reorder_task_capability')
                  return (
                    (en.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'reorder_task_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.capability_id !== void 0) {
                    let n = c;
                    s(e.capability_id, {
                      instancePath: t + '/capability_id',
                      parentData: e,
                      parentDataProperty: 'capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.before_capability_id !== void 0) {
                      let n = e.before_capability_id,
                        r = c,
                        l = c,
                        f = !1,
                        p = c;
                      s(n, {
                        instancePath: t + '/before_capability_id',
                        parentData: e,
                        parentDataProperty: 'before_capability_id',
                        rootData: i,
                        dynamicAnchors: a,
                      }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                      var d = p === c;
                      f ||= d;
                      let m = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/before_capability_id',
                          schemaPath: '#/properties/before_capability_id/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var d = m === c;
                      if (((f ||= d), f))
                        ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/before_capability_id',
                          schemaPath: '#/properties/before_capability_id/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (en.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (en.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((en.errors = o), c === 0);
    }
    ((en.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseArea = tn));
    function tn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = tn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (tn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'area_id' && n !== 'changes')
                return (
                  (tn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (tn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_area')
                  return (
                    (tn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_area' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = c;
                  s(e.area_id, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (tn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (tn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (_(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? _.errors : o.concat(_.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (tn.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (tn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((tn.errors = o), c === 0);
    }
    ((tn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseCapability = nn));
    function nn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = nn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (nn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'capability_id' && n !== 'changes')
                return (
                  (nn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (nn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_capability')
                  return (
                    (nn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (nn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (nn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (ze(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? ze.errors : o.concat(ze.errors)),
                                (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (nn.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (nn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((nn.errors = o), c === 0);
    }
    ((nn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseCollaborator = rn));
    function rn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = rn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.collaborator_id === void 0 && (n = 'collaborator_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (rn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'collaborator_id' && n !== 'changes')
                return (
                  (rn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (rn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_collaborator')
                  return (
                    (rn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_collaborator' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.collaborator_id !== void 0) {
                  let n = c;
                  s(e.collaborator_id, {
                    instancePath: t + '/collaborator_id',
                    parentData: e,
                    parentDataProperty: 'collaborator_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (rn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (rn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (he(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? he.errors : o.concat(he.errors)),
                                (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (rn.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (rn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((rn.errors = o), c === 0);
    }
    ((rn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseCondition = an));
    function an(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = an.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.condition_id === void 0 && (n = 'condition_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (an.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'condition_id' && n !== 'changes')
                return (
                  (an.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (an.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_condition')
                  return (
                    (an.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_condition' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.condition_id !== void 0) {
                  let n = c;
                  s(e.condition_id, {
                    instancePath: t + '/condition_id',
                    parentData: e,
                    parentDataProperty: 'condition_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 2)
                          return (
                            (an.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 2 },
                                message: 'must NOT have more than 2 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (an.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = n[r],
                              s = c,
                              l = c,
                              u = !1,
                              p = null,
                              m = c;
                            j(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? j.errors : o.concat(j.errors)), (c = o.length));
                            var d = m === c;
                            if (d) {
                              ((u = !0), (p = 0));
                              var f = !0;
                            }
                            let h = c;
                            A(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? A.errors : o.concat(A.errors)), (c = o.length));
                            var d = h === c;
                            if (
                              (d && u
                                ? ((u = !1), (p = [p, 1]))
                                : d && ((u = !0), (p = 1), f !== !0 && (f = !0)),
                              u)
                            )
                              ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                            else {
                              let e = {
                                instancePath: t + '/changes/' + r,
                                schemaPath: '#/properties/changes/items/oneOf',
                                keyword: 'oneOf',
                                params: { passingSchemas: p },
                                message: 'must match exactly one schema in oneOf',
                              };
                              return (o === null ? (o = [e]) : o.push(e), c++, (an.errors = o), !1);
                            }
                            if (s !== c) break;
                          }
                        }
                      } else
                        return (
                          (an.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (an.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((an.errors = o), c === 0);
    }
    ((an.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseDetail = on));
    function on(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = on.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.detail_id === void 0 && (n = 'detail_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (on.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'detail_id' && n !== 'text')
                return (
                  (on.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (on.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_detail')
                  return (
                    (on.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_detail' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.detail_id !== void 0) {
                  let n = c;
                  s(e.detail_id, {
                    instancePath: t + '/detail_id',
                    parentData: e,
                    parentDataProperty: 'detail_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.text !== void 0) {
                    let n = c;
                    f(e.text, {
                      instancePath: t + '/text',
                      parentData: e,
                      parentDataProperty: 'text',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (on.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((on.errors = o), c === 0);
    }
    ((on.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseJdProfileRequest = cn));
    function sn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = sn.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.field === void 0 && (n = 'field')) ||
            (e.value === void 0 && (n = 'value'))
          )
            return (
              (sn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'action' && n !== 'field' && n !== 'value')
                return (
                  (sn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = s;
                if (typeof n != 'string')
                  return (
                    (sn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'set_field')
                  return (
                    (sn.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'set_field' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var l = r === s;
              } else var l = !0;
              if (l) {
                if (e.field !== void 0) {
                  let n = s;
                  k(e.field, {
                    instancePath: t + '/field',
                    parentData: e,
                    parentDataProperty: 'field',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? k.errors : o.concat(k.errors)), (s = o.length));
                  var l = n === s;
                } else var l = !0;
                if (l) {
                  if (e.value !== void 0) {
                    let n = s;
                    f(e.value, {
                      instancePath: t + '/value',
                      parentData: e,
                      parentDataProperty: 'value',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? f.errors : o.concat(f.errors)), (s = o.length));
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (sn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((sn.errors = o), s === 0);
    }
    sn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
    function cn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = cn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.expected_revision_id === void 0 && (n = 'expected_revision_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (cn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'expected_revision_id' && n !== 'changes')
                return (
                  (cn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.expected_revision_id !== void 0) {
                  let n = c;
                  s(e.expected_revision_id, {
                    instancePath: t + '/expected_revision_id',
                    parentData: e,
                    parentDataProperty: 'expected_revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length > 4)
                          return (
                            (cn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/maxItems',
                                keyword: 'maxItems',
                                params: { limit: 4 },
                                message: 'must NOT have more than 4 items',
                              },
                            ]),
                            !1
                          );
                        if (n.length < 1)
                          return (
                            (cn.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = n[r],
                              s = c,
                              l = c,
                              u = !1,
                              p = null,
                              m = c;
                            sn(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? sn.errors : o.concat(sn.errors)), (c = o.length));
                            var d = m === c;
                            if (d) {
                              ((u = !0), (p = 0));
                              var f = !0;
                            }
                            let h = c;
                            de(e, {
                              instancePath: t + '/changes/' + r,
                              parentData: n,
                              parentDataProperty: r,
                              rootData: i,
                              dynamicAnchors: a,
                            }) ||
                              ((o = o === null ? de.errors : o.concat(de.errors)), (c = o.length));
                            var d = h === c;
                            if (
                              (d && u
                                ? ((u = !1), (p = [p, 1]))
                                : d && ((u = !0), (p = 1), f !== !0 && (f = !0)),
                              u)
                            )
                              ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                            else {
                              let e = {
                                instancePath: t + '/changes/' + r,
                                schemaPath: '#/properties/changes/items/oneOf',
                                keyword: 'oneOf',
                                params: { passingSchemas: p },
                                message: 'must match exactly one schema in oneOf',
                              };
                              return (o === null ? (o = [e]) : o.push(e), c++, (cn.errors = o), !1);
                            }
                            if (s !== c) break;
                          }
                        }
                      } else
                        return (
                          (cn.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (cn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((cn.errors = o), c === 0);
    }
    ((cn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isReviseTask = ln));
    function ln(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = ln.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.changes === void 0 && (n = 'changes'))
          )
            return (
              (ln.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'task_id' && n !== 'changes')
                return (
                  (ln.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (ln.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'revise_task')
                  return (
                    (ln.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'revise_task' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.changes !== void 0) {
                    let n = e.changes,
                      r = c;
                    if (c === r) {
                      if (Array.isArray(n)) {
                        if (n.length < 1)
                          return (
                            (ln.errors = [
                              {
                                instancePath: t + '/changes',
                                schemaPath: '#/properties/changes/minItems',
                                keyword: 'minItems',
                                params: { limit: 1 },
                                message: 'must NOT have fewer than 1 items',
                              },
                            ]),
                            !1
                          );
                        {
                          let e = n.length;
                          for (let r = 0; r < e; r++) {
                            let e = c;
                            if (
                              (K(n[r], {
                                instancePath: t + '/changes/' + r,
                                parentData: n,
                                parentDataProperty: r,
                                rootData: i,
                                dynamicAnchors: a,
                              }) ||
                                ((o = o === null ? K.errors : o.concat(K.errors)), (c = o.length)),
                              e !== c)
                            )
                              break;
                          }
                        }
                      } else
                        return (
                          (ln.errors = [
                            {
                              instancePath: t + '/changes',
                              schemaPath: '#/properties/changes/type',
                              keyword: 'type',
                              params: { type: 'array' },
                              message: 'must be array',
                            },
                          ]),
                          !1
                        );
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (ln.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((ln.errors = o), c === 0);
    }
    ((ln.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isSetTaskCapability = un));
    function un(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = un.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.action === void 0 && (n = 'action')) ||
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id')) ||
            (e.linked === void 0 && (n = 'linked'))
          )
            return (
              (un.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'action' && n !== 'task_id' && n !== 'capability_id' && n !== 'linked')
                return (
                  (un.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.action !== void 0) {
                let n = e.action,
                  r = c;
                if (typeof n != 'string')
                  return (
                    (un.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      },
                    ]),
                    !1
                  );
                if (n !== 'set_task_capability')
                  return (
                    (un.errors = [
                      {
                        instancePath: t + '/action',
                        schemaPath: '#/properties/action/const',
                        keyword: 'const',
                        params: { allowedValue: 'set_task_capability' },
                        message: 'must be equal to constant',
                      },
                    ]),
                    !1
                  );
                var u = r === c;
              } else var u = !0;
              if (u) {
                if (e.task_id !== void 0) {
                  let n = c;
                  s(e.task_id, {
                    instancePath: t + '/task_id',
                    parentData: e,
                    parentDataProperty: 'task_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
                if (u) {
                  if (e.capability_id !== void 0) {
                    let n = c;
                    s(e.capability_id, {
                      instancePath: t + '/capability_id',
                      parentData: e,
                      parentDataProperty: 'capability_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                  if (u) {
                    if (e.linked !== void 0) {
                      let n = c;
                      if (typeof e.linked != 'boolean')
                        return (
                          (un.errors = [
                            {
                              instancePath: t + '/linked',
                              schemaPath: '#/properties/linked/type',
                              keyword: 'type',
                              params: { type: 'boolean' },
                              message: 'must be boolean',
                            },
                          ]),
                          !1
                        );
                      var u = n === c;
                    } else var u = !0;
                  }
                }
              }
            }
          }
        } else
          return (
            (un.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((un.errors = o), c === 0);
    }
    ((un.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isSourceLink = dn));
    function dn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = dn.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.source_ref === void 0 && (n = 'source_ref')) ||
            (e.kind === void 0 && (n = 'kind')) ||
            (e.label === void 0 && (n = 'label'))
          )
            return (
              (dn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = s;
            for (let n in e)
              if (n !== 'source_ref' && n !== 'kind' && n !== 'label')
                return (
                  (dn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === s) {
              if (e.source_ref !== void 0) {
                let n = s;
                M(e.source_ref, {
                  instancePath: t + '/source_ref',
                  parentData: e,
                  parentDataProperty: 'source_ref',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? M.errors : o.concat(M.errors)), (s = o.length));
                var l = n === s;
              } else var l = !0;
              if (l) {
                if (e.kind !== void 0) {
                  let n = e.kind,
                    r = s;
                  if (typeof n != 'string')
                    return (
                      (dn.errors = [
                        {
                          instancePath: t + '/kind',
                          schemaPath: '#/properties/kind/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  if (n !== 'interview' && n !== 'work_situation')
                    return (
                      (dn.errors = [
                        {
                          instancePath: t + '/kind',
                          schemaPath: '#/properties/kind/enum',
                          keyword: 'enum',
                          params: { allowedValues: bt.properties.kind.enum },
                          message: 'must be equal to one of the allowed values',
                        },
                      ]),
                      !1
                    );
                  var l = r === s;
                } else var l = !0;
                if (l) {
                  if (e.label !== void 0) {
                    let n = s;
                    if (typeof e.label != 'string')
                      return (
                        (dn.errors = [
                          {
                            instancePath: t + '/label',
                            schemaPath: '#/properties/label/type',
                            keyword: 'type',
                            params: { type: 'string' },
                            message: 'must be string',
                          },
                        ]),
                        !1
                      );
                    var l = n === s;
                  } else var l = !0;
                }
              }
            }
          }
        } else
          return (
            (dn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((dn.errors = o), s === 0);
    }
    ((dn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isSourceTargetKind = fn));
    function fn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = fn.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'profile_field' &&
            e !== 'area' &&
            e !== 'task' &&
            e !== 'capability' &&
            e !== 'collaborator' &&
            e !== 'condition'
            ? ((fn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Tt.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((fn.errors = null), !0)
          : ((fn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((fn.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isSourceVersion = pn));
    function pn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = pn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.snapshot_id === void 0 && (n = 'snapshot_id')) ||
            (e.revision_id === void 0 && (n = 'revision_id')) ||
            (e.covered_through_sequence === void 0 && (n = 'covered_through_sequence'))
          )
            return (
              (pn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'snapshot_id' && n !== 'revision_id' && n !== 'covered_through_sequence')
                return (
                  (pn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.snapshot_id !== void 0) {
                let n = c;
                s(e.snapshot_id, {
                  instancePath: t + '/snapshot_id',
                  parentData: e,
                  parentDataProperty: 'snapshot_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.revision_id !== void 0) {
                  let n = e.revision_id,
                    r = c,
                    l = c,
                    f = !1,
                    p = c;
                  s(n, {
                    instancePath: t + '/revision_id',
                    parentData: e,
                    parentDataProperty: 'revision_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = p === c;
                  f ||= d;
                  let m = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/revision_id',
                      schemaPath: '#/properties/revision_id/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = m === c;
                  if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/revision_id',
                      schemaPath: '#/properties/revision_id/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (pn.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.covered_through_sequence !== void 0) {
                    let n = c;
                    q(e.covered_through_sequence, {
                      instancePath: t + '/covered_through_sequence',
                      parentData: e,
                      parentDataProperty: 'covered_through_sequence',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? q.errors : o.concat(q.errors)), (c = o.length));
                    var u = n === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (pn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((pn.errors = o), c === 0);
    }
    ((pn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isSubmitInterviewInput = mn));
    function mn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = mn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.command_id === void 0 && (n = 'command_id')) ||
            (e.text === void 0 && (n = 'text'))
          )
            return (
              (mn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'command_id' && n !== 'text')
                return (
                  (mn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.command_id !== void 0) {
                let n = c;
                s(e.command_id, {
                  instancePath: t + '/command_id',
                  parentData: e,
                  parentDataProperty: 'command_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.text !== void 0) {
                  let n = c;
                  f(e.text, {
                    instancePath: t + '/text',
                    parentData: e,
                    parentDataProperty: 'text',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? f.errors : o.concat(f.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (mn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((mn.errors = o), c === 0);
    }
    ((mn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isTarget = hn));
    function hn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = hn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.kind === void 0 && (n = 'kind')) ||
            (e.field === void 0 && (n = 'field')) ||
            (e.item_id === void 0 && (n = 'item_id'))
          )
            return (
              (hn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'kind' && n !== 'field' && n !== 'item_id')
                return (
                  (hn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.kind !== void 0) {
                let n = c;
                Et(e.kind, {
                  instancePath: t + '/kind',
                  parentData: e,
                  parentDataProperty: 'kind',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? Et.errors : o.concat(Et.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.field !== void 0) {
                  let n = e.field,
                    r = c,
                    s = c,
                    l = !1,
                    f = c;
                  k(n, {
                    instancePath: t + '/field',
                    parentData: e,
                    parentDataProperty: 'field',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? k.errors : o.concat(k.errors)), (c = o.length));
                  var d = f === c;
                  l ||= d;
                  let p = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/field',
                      schemaPath: '#/properties/field/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = p === c;
                  if (((l ||= d), l)) ((c = s), o !== null && (s ? (o.length = s) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/field',
                      schemaPath: '#/properties/field/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (hn.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.item_id !== void 0) {
                    let n = e.item_id,
                      r = c,
                      l = c,
                      d = !1,
                      p = c;
                    s(n, {
                      instancePath: t + '/item_id',
                      parentData: e,
                      parentDataProperty: 'item_id',
                      rootData: i,
                      dynamicAnchors: a,
                    }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                    var f = p === c;
                    d ||= f;
                    let m = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/item_id',
                        schemaPath: '#/properties/item_id/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = m === c;
                    if (((d ||= f), d)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/item_id',
                        schemaPath: '#/properties/item_id/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (hn.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                }
              }
            }
          }
        } else
          return (
            (hn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((hn.errors = o), c === 0);
    }
    ((hn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isTaskChange = gn));
    function gn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = gn.evaluated;
      (c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0));
      let l = s,
        u = !1,
        d = null,
        f = s;
      U(e, {
        instancePath: t,
        parentData: n,
        parentDataProperty: r,
        rootData: i,
        dynamicAnchors: a,
      }) || ((o = o === null ? U.errors : o.concat(U.errors)), (s = o.length));
      var m = f === s;
      if (m) {
        ((u = !0), (d = 0));
        var h = !0;
      }
      let g = s;
      p(e, {
        instancePath: t,
        parentData: n,
        parentDataProperty: r,
        rootData: i,
        dynamicAnchors: a,
      }) || ((o = o === null ? p.errors : o.concat(p.errors)), (s = o.length));
      var m = g === s;
      if (m && u) ((u = !1), (d = [d, 1]));
      else {
        m && ((u = !0), (d = 1), h !== !0 && (h = !0));
        let c = s;
        W(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? W.errors : o.concat(W.errors)), (s = o.length));
        var m = c === s;
        if (m && u) ((u = !1), (d = [d, 2]));
        else {
          m && ((u = !0), (d = 2), h !== !0 && (h = !0));
          let c = s;
          G(e, {
            instancePath: t,
            parentData: n,
            parentDataProperty: r,
            rootData: i,
            dynamicAnchors: a,
          }) || ((o = o === null ? G.errors : o.concat(G.errors)), (s = o.length));
          var m = c === s;
          m && u ? ((u = !1), (d = [d, 3])) : m && ((u = !0), (d = 3), h !== !0 && (h = !0));
        }
      }
      if (u) ((s = l), o !== null && (l ? (o.length = l) : (o = null)));
      else {
        let e = {
          instancePath: t,
          schemaPath: '#/oneOf',
          keyword: 'oneOf',
          params: { passingSchemas: d },
          message: 'must match exactly one schema in oneOf',
        };
        return (o === null ? (o = [e]) : o.push(e), s++, (gn.errors = o), !1);
      }
      return ((gn.errors = o), (c.props = h), s === 0);
    }
    ((gn.evaluated = {
      dynamicProps: !0,
      dynamicItems: !1,
    }),
      (e.isTaskField = _n));
    function _n(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = _n.evaluated;
      return (
        o.dynamicProps && (o.props = void 0),
        o.dynamicItems && (o.items = void 0),
        typeof e == 'string'
          ? e !== 'title' && e !== 'description'
            ? ((_n.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/enum',
                  keyword: 'enum',
                  params: { allowedValues: Je.enum },
                  message: 'must be equal to one of the allowed values',
                },
              ]),
              !1)
            : ((_n.errors = null), !0)
          : ((_n.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'string' },
                message: 'must be string',
              },
            ]),
            !1)
      );
    }
    ((_n.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isTaskLink = vn));
    function vn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = vn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.capability_id === void 0 && (n = 'capability_id'))
          )
            return (
              (vn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'task_id' && n !== 'capability_id')
                return (
                  (vn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.task_id !== void 0) {
                let n = c;
                s(e.task_id, {
                  instancePath: t + '/task_id',
                  parentData: e,
                  parentDataProperty: 'task_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.capability_id !== void 0) {
                  let n = c;
                  s(e.capability_id, {
                    instancePath: t + '/capability_id',
                    parentData: e,
                    parentDataProperty: 'capability_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (vn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((vn.errors = o), c === 0);
    }
    ((vn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isTurnJdChanges = yn));
    function yn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = yn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.execution_id === void 0 && (n = 'execution_id')) ||
            (e.markdown === void 0 && (n = 'markdown'))
          )
            return (
              (yn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'execution_id' && n !== 'markdown')
                return (
                  (yn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.execution_id !== void 0) {
                let n = c;
                s(e.execution_id, {
                  instancePath: t + '/execution_id',
                  parentData: e,
                  parentDataProperty: 'execution_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.markdown !== void 0) {
                  let n = c;
                  if (typeof e.markdown != 'string')
                    return (
                      (yn.errors = [
                        {
                          instancePath: t + '/markdown',
                          schemaPath: '#/properties/markdown/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        },
                      ]),
                      !1
                    );
                  var u = n === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (yn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((yn.errors = o), c === 0);
    }
    ((yn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isTurnTools = bn));
    function bn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = bn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.execution_id === void 0 && (n = 'execution_id')) ||
            (e.calls === void 0 && (n = 'calls'))
          )
            return (
              (bn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (n !== 'execution_id' && n !== 'calls')
                return (
                  (bn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.execution_id !== void 0) {
                let n = c;
                s(e.execution_id, {
                  instancePath: t + '/execution_id',
                  parentData: e,
                  parentDataProperty: 'execution_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.calls !== void 0) {
                  let n = e.calls,
                    r = c;
                  if (c === r) {
                    if (Array.isArray(n)) {
                      let e = n.length;
                      for (let r = 0; r < e; r++) {
                        let e = c;
                        if (
                          (v(n[r], {
                            instancePath: t + '/calls/' + r,
                            parentData: n,
                            parentDataProperty: r,
                            rootData: i,
                            dynamicAnchors: a,
                          }) || ((o = o === null ? v.errors : o.concat(v.errors)), (c = o.length)),
                          e !== c)
                        )
                          break;
                      }
                    } else
                      return (
                        (bn.errors = [
                          {
                            instancePath: t + '/calls',
                            schemaPath: '#/properties/calls/type',
                            keyword: 'type',
                            params: { type: 'array' },
                            message: 'must be array',
                          },
                        ]),
                        !1
                      );
                  }
                  var u = r === c;
                } else var u = !0;
              }
            }
          }
        } else
          return (
            (bn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((bn.errors = o), c === 0);
    }
    ((bn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isWireUuid = xn));
    function xn(
      e,
      {
        instancePath: t = '',
        parentData: r,
        parentDataProperty: i,
        rootData: s = e,
        dynamicAnchors: c = {},
      } = {},
    ) {
      let l = xn.evaluated;
      if (
        (l.dynamicProps && (l.props = void 0),
        l.dynamicItems && (l.items = void 0),
        typeof e == 'string')
      ) {
        if (a(e) > 36)
          return (
            (xn.errors = [
              {
                instancePath: t,
                schemaPath: '#/maxLength',
                keyword: 'maxLength',
                params: { limit: 36 },
                message: 'must NOT have more than 36 characters',
              },
            ]),
            !1
          );
        if (a(e) < 36)
          return (
            (xn.errors = [
              {
                instancePath: t,
                schemaPath: '#/minLength',
                keyword: 'minLength',
                params: { limit: 36 },
                message: 'must NOT have fewer than 36 characters',
              },
            ]),
            !1
          );
        if (!o.test(e))
          return (
            (xn.errors = [
              {
                instancePath: t,
                schemaPath: '#/pattern',
                keyword: 'pattern',
                params: {
                  pattern:
                    '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
                },
                message:
                  'must match pattern "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"',
              },
            ]),
            !1
          );
        if (!n.test(e))
          return (
            (xn.errors = [
              {
                instancePath: t,
                schemaPath: '#/format',
                keyword: 'format',
                params: { format: 'uuid' },
                message: 'must match format "uuid"',
              },
            ]),
            !1
          );
      } else
        return (
          (xn.errors = [
            {
              instancePath: t,
              schemaPath: '#/type',
              keyword: 'type',
              params: { type: 'string' },
              message: 'must be string',
            },
          ]),
          !1
        );
      return ((xn.errors = null), !0);
    }
    ((xn.evaluated = {
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.isWorkTask = Sn));
    function Sn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        c = 0,
        l = Sn.evaluated;
      if ((l.dynamicProps && (l.props = void 0), l.dynamicItems && (l.items = void 0), c === 0)) {
        if (e && typeof e == 'object' && !Array.isArray(e)) {
          let n;
          if (
            (e.task_id === void 0 && (n = 'task_id')) ||
            (e.area_id === void 0 && (n = 'area_id')) ||
            (e.title === void 0 && (n = 'title')) ||
            (e.description === void 0 && (n = 'description')) ||
            (e.outcomes === void 0 && (n = 'outcomes')) ||
            (e.requirements === void 0 && (n = 'requirements'))
          )
            return (
              (Sn.errors = [
                {
                  instancePath: t,
                  schemaPath: '#/required',
                  keyword: 'required',
                  params: { missingProperty: n },
                  message: "must have required property '" + n + "'",
                },
              ]),
              !1
            );
          {
            let n = c;
            for (let n in e)
              if (
                n !== 'task_id' &&
                n !== 'area_id' &&
                n !== 'title' &&
                n !== 'description' &&
                n !== 'outcomes' &&
                n !== 'requirements'
              )
                return (
                  (Sn.errors = [
                    {
                      instancePath: t,
                      schemaPath: '#/additionalProperties',
                      keyword: 'additionalProperties',
                      params: { additionalProperty: n },
                      message: 'must NOT have additional properties',
                    },
                  ]),
                  !1
                );
            if (n === c) {
              if (e.task_id !== void 0) {
                let n = c;
                s(e.task_id, {
                  instancePath: t + '/task_id',
                  parentData: e,
                  parentDataProperty: 'task_id',
                  rootData: i,
                  dynamicAnchors: a,
                }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                var u = n === c;
              } else var u = !0;
              if (u) {
                if (e.area_id !== void 0) {
                  let n = e.area_id,
                    r = c,
                    l = c,
                    f = !1,
                    p = c;
                  s(n, {
                    instancePath: t + '/area_id',
                    parentData: e,
                    parentDataProperty: 'area_id',
                    rootData: i,
                    dynamicAnchors: a,
                  }) || ((o = o === null ? s.errors : o.concat(s.errors)), (c = o.length));
                  var d = p === c;
                  f ||= d;
                  let m = c;
                  if (n !== null) {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf/1/type',
                      keyword: 'type',
                      params: { type: 'null' },
                      message: 'must be null',
                    };
                    (o === null ? (o = [e]) : o.push(e), c++);
                  }
                  var d = m === c;
                  if (((f ||= d), f)) ((c = l), o !== null && (l ? (o.length = l) : (o = null)));
                  else {
                    let e = {
                      instancePath: t + '/area_id',
                      schemaPath: '#/properties/area_id/anyOf',
                      keyword: 'anyOf',
                      params: {},
                      message: 'must match a schema in anyOf',
                    };
                    return (o === null ? (o = [e]) : o.push(e), c++, (Sn.errors = o), !1);
                  }
                  var u = r === c;
                } else var u = !0;
                if (u) {
                  if (e.title !== void 0) {
                    let n = e.title,
                      r = c,
                      i = c,
                      a = !1,
                      s = c;
                    if (typeof n != 'string') {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf/0/type',
                        keyword: 'type',
                        params: { type: 'string' },
                        message: 'must be string',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = s === c;
                    a ||= f;
                    let l = c;
                    if (n !== null) {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf/1/type',
                        keyword: 'type',
                        params: { type: 'null' },
                        message: 'must be null',
                      };
                      (o === null ? (o = [e]) : o.push(e), c++);
                    }
                    var f = l === c;
                    if (((a ||= f), a)) ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                    else {
                      let e = {
                        instancePath: t + '/title',
                        schemaPath: '#/properties/title/anyOf',
                        keyword: 'anyOf',
                        params: {},
                        message: 'must match a schema in anyOf',
                      };
                      return (o === null ? (o = [e]) : o.push(e), c++, (Sn.errors = o), !1);
                    }
                    var u = r === c;
                  } else var u = !0;
                  if (u) {
                    if (e.description !== void 0) {
                      let n = e.description,
                        r = c,
                        i = c,
                        a = !1,
                        s = c;
                      if (typeof n != 'string') {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/0/type',
                          keyword: 'type',
                          params: { type: 'string' },
                          message: 'must be string',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var p = s === c;
                      a ||= p;
                      let l = c;
                      if (n !== null) {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf/1/type',
                          keyword: 'type',
                          params: { type: 'null' },
                          message: 'must be null',
                        };
                        (o === null ? (o = [e]) : o.push(e), c++);
                      }
                      var p = l === c;
                      if (((a ||= p), a))
                        ((c = i), o !== null && (i ? (o.length = i) : (o = null)));
                      else {
                        let e = {
                          instancePath: t + '/description',
                          schemaPath: '#/properties/description/anyOf',
                          keyword: 'anyOf',
                          params: {},
                          message: 'must match a schema in anyOf',
                        };
                        return (o === null ? (o = [e]) : o.push(e), c++, (Sn.errors = o), !1);
                      }
                      var u = r === c;
                    } else var u = !0;
                    if (u) {
                      if (e.outcomes !== void 0) {
                        let n = e.outcomes,
                          r = c;
                        if (c === r) {
                          if (Array.isArray(n)) {
                            let e = n.length;
                            for (let r = 0; r < e; r++) {
                              let e = c;
                              if (
                                (b(n[r], {
                                  instancePath: t + '/outcomes/' + r,
                                  parentData: n,
                                  parentDataProperty: r,
                                  rootData: i,
                                  dynamicAnchors: a,
                                }) ||
                                  ((o = o === null ? b.errors : o.concat(b.errors)),
                                  (c = o.length)),
                                e !== c)
                              )
                                break;
                            }
                          } else
                            return (
                              (Sn.errors = [
                                {
                                  instancePath: t + '/outcomes',
                                  schemaPath: '#/properties/outcomes/type',
                                  keyword: 'type',
                                  params: { type: 'array' },
                                  message: 'must be array',
                                },
                              ]),
                              !1
                            );
                        }
                        var u = r === c;
                      } else var u = !0;
                      if (u) {
                        if (e.requirements !== void 0) {
                          let n = e.requirements,
                            r = c;
                          if (c === r) {
                            if (Array.isArray(n)) {
                              let e = n.length;
                              for (let r = 0; r < e; r++) {
                                let e = c;
                                if (
                                  (b(n[r], {
                                    instancePath: t + '/requirements/' + r,
                                    parentData: n,
                                    parentDataProperty: r,
                                    rootData: i,
                                    dynamicAnchors: a,
                                  }) ||
                                    ((o = o === null ? b.errors : o.concat(b.errors)),
                                    (c = o.length)),
                                  e !== c)
                                )
                                  break;
                              }
                            } else
                              return (
                                (Sn.errors = [
                                  {
                                    instancePath: t + '/requirements',
                                    schemaPath: '#/properties/requirements/type',
                                    keyword: 'type',
                                    params: { type: 'array' },
                                    message: 'must be array',
                                  },
                                ]),
                                !1
                              );
                          }
                          var u = r === c;
                        } else var u = !0;
                      }
                    }
                  }
                }
              }
            }
          }
        } else
          return (
            (Sn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'object' },
                message: 'must be object',
              },
            ]),
            !1
          );
      }
      return ((Sn.errors = o), c === 0);
    }
    ((Sn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response0 = Cn));
    function Cn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Cn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        nt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? nt.errors : o.concat(nt.errors)), (s = o.length)),
        (Cn.errors = o),
        s === 0
      );
    }
    ((Cn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response2 = wn));
    function wn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = wn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Q(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Q.errors : o.concat(Q.errors)), (s = o.length)),
        (wn.errors = o),
        s === 0
      );
    }
    ((wn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response3 = Tn));
    function Tn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Tn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        jt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? jt.errors : o.concat(jt.errors)), (s = o.length)),
        (Tn.errors = o),
        s === 0
      );
    }
    ((Tn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response4 = En));
    function En(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = En.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Q(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Q.errors : o.concat(Q.errors)), (s = o.length)),
        (En.errors = o),
        s === 0
      );
    }
    ((En.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response5 = Dn));
    function Dn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Dn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Q(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Q.errors : o.concat(Q.errors)), (s = o.length)),
        (Dn.errors = o),
        s === 0
      );
    }
    ((Dn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response6 = On));
    function On(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = On.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        ct(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? ct.errors : o.concat(ct.errors)), (s = o.length)),
        (On.errors = o),
        s === 0
      );
    }
    ((On.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response7 = kn));
    function kn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = kn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Q(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Q.errors : o.concat(Q.errors)), (s = o.length)),
        (kn.errors = o),
        s === 0
      );
    }
    ((kn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response8 = An));
    function An(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        l = An.evaluated;
      return (
        l.dynamicProps && (l.props = void 0),
        l.dynamicItems && (l.items = void 0),
        c(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? c.errors : o.concat(c.errors)), (s = o.length)),
        (An.errors = o),
        s === 0
      );
    }
    ((An.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response9 = jn));
    function jn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        l = jn.evaluated;
      return (
        l.dynamicProps && (l.props = void 0),
        l.dynamicItems && (l.items = void 0),
        c(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? c.errors : o.concat(c.errors)), (s = o.length)),
        (jn.errors = o),
        s === 0
      );
    }
    ((jn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response10 = Mn));
    function Mn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Mn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        dt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? dt.errors : o.concat(dt.errors)), (s = o.length)),
        (Mn.errors = o),
        s === 0
      );
    }
    ((Mn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response11 = Nn));
    function Nn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Nn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Oe(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Oe.errors : o.concat(Oe.errors)), (s = o.length)),
        (Nn.errors = o),
        s === 0
      );
    }
    ((Nn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response12 = Pn));
    function Pn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Pn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        N(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length)),
        (Pn.errors = o),
        s === 0
      );
    }
    ((Pn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response13 = Fn));
    function Fn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Fn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        N(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length)),
        (Fn.errors = o),
        s === 0
      );
    }
    ((Fn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response14 = In));
    function In(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = In.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        N(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length)),
        (In.errors = o),
        s === 0
      );
    }
    ((In.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response15 = Ln));
    function Ln(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Ln.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        N(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length)),
        (Ln.errors = o),
        s === 0
      );
    }
    ((Ln.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response16 = Rn));
    function Rn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Rn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        N(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? N.errors : o.concat(N.errors)), (s = o.length)),
        (Rn.errors = o),
        s === 0
      );
    }
    ((Rn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response17 = zn));
    function zn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = zn.evaluated;
      if ((c.dynamicProps && (c.props = void 0), c.dynamicItems && (c.items = void 0), s === 0)) {
        if (Array.isArray(e)) {
          let n = e.length;
          for (let r = 0; r < n; r++) {
            let n = s;
            if (
              (Gt(e[r], {
                instancePath: t + '/' + r,
                parentData: e,
                parentDataProperty: r,
                rootData: i,
                dynamicAnchors: a,
              }) || ((o = o === null ? Gt.errors : o.concat(Gt.errors)), (s = o.length)),
              n !== s)
            )
              break;
          }
        } else
          return (
            (zn.errors = [
              {
                instancePath: t,
                schemaPath: '#/type',
                keyword: 'type',
                params: { type: 'array' },
                message: 'must be array',
              },
            ]),
            !1
          );
      }
      return ((zn.errors = o), s === 0);
    }
    ((zn.evaluated = {
      items: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response20 = Bn));
    function Bn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Bn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Y(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Y.errors : o.concat(Y.errors)), (s = o.length)),
        (Bn.errors = o),
        s === 0
      );
    }
    ((Bn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response21 = Vn));
    function Vn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Vn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Y(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Y.errors : o.concat(Y.errors)), (s = o.length)),
        (Vn.errors = o),
        s === 0
      );
    }
    ((Vn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response22 = Hn));
    function Hn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Hn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        pt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? pt.errors : o.concat(pt.errors)), (s = o.length)),
        (Hn.errors = o),
        s === 0
      );
    }
    ((Hn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response23 = Un));
    function Un(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Un.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        pt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? pt.errors : o.concat(pt.errors)), (s = o.length)),
        (Un.errors = o),
        s === 0
      );
    }
    ((Un.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response24 = Wn));
    function Wn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Wn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        mt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? mt.errors : o.concat(mt.errors)), (s = o.length)),
        (Wn.errors = o),
        s === 0
      );
    }
    ((Wn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response25 = Gn));
    function Gn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Gn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        mt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? mt.errors : o.concat(mt.errors)), (s = o.length)),
        (Gn.errors = o),
        s === 0
      );
    }
    ((Gn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response26 = Kn));
    function Kn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Kn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        ht(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? ht.errors : o.concat(ht.errors)), (s = o.length)),
        (Kn.errors = o),
        s === 0
      );
    }
    ((Kn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response27 = qn));
    function qn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = qn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        ht(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? ht.errors : o.concat(ht.errors)), (s = o.length)),
        (qn.errors = o),
        s === 0
      );
    }
    ((qn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response28 = Jn));
    function Jn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Jn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        gt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? gt.errors : o.concat(gt.errors)), (s = o.length)),
        (Jn.errors = o),
        s === 0
      );
    }
    ((Jn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response29 = Yn));
    function Yn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Yn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        gt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? gt.errors : o.concat(gt.errors)), (s = o.length)),
        (Yn.errors = o),
        s === 0
      );
    }
    ((Yn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response30 = Xn));
    function Xn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Xn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        kt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? kt.errors : o.concat(kt.errors)), (s = o.length)),
        (Xn.errors = o),
        s === 0
      );
    }
    ((Xn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response31 = Zn));
    function Zn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Zn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        kt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? kt.errors : o.concat(kt.errors)), (s = o.length)),
        (Zn.errors = o),
        s === 0
      );
    }
    ((Zn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response32 = Qn));
    function Qn(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = Qn.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Z(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Z.errors : o.concat(Z.errors)), (s = o.length)),
        (Qn.errors = o),
        s === 0
      );
    }
    ((Qn.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response33 = $n));
    function $n(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = $n.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Ot(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Ot.errors : o.concat(Ot.errors)), (s = o.length)),
        ($n.errors = o),
        s === 0
      );
    }
    (($n.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response34 = er));
    function er(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = er.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Ct(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Ct.errors : o.concat(Ct.errors)), (s = o.length)),
        (er.errors = o),
        s === 0
      );
    }
    ((er.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response35 = tr));
    function tr(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = tr.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        vt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? vt.errors : o.concat(vt.errors)), (s = o.length)),
        (tr.errors = o),
        s === 0
      );
    }
    ((tr.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response37 = nr));
    function nr(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = nr.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Y(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Y.errors : o.concat(Y.errors)), (s = o.length)),
        (nr.errors = o),
        s === 0
      );
    }
    ((nr.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response38 = rr));
    function rr(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = rr.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        yn(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? yn.errors : o.concat(yn.errors)), (s = o.length)),
        (rr.errors = o),
        s === 0
      );
    }
    ((rr.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response39 = ir));
    function ir(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ir.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        bn(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? bn.errors : o.concat(bn.errors)), (s = o.length)),
        (ir.errors = o),
        s === 0
      );
    }
    ((ir.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response40 = ar));
    function ar(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = ar.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Ut(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Ut.errors : o.concat(Ut.errors)), (s = o.length)),
        (ar.errors = o),
        s === 0
      );
    }
    ((ar.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    }),
      (e.response41 = or));
    function or(
      e,
      {
        instancePath: t = '',
        parentData: n,
        parentDataProperty: r,
        rootData: i = e,
        dynamicAnchors: a = {},
      } = {},
    ) {
      let o = null,
        s = 0,
        c = or.evaluated;
      return (
        c.dynamicProps && (c.props = void 0),
        c.dynamicItems && (c.items = void 0),
        Wt(e, {
          instancePath: t,
          parentData: n,
          parentDataProperty: r,
          rootData: i,
          dynamicAnchors: a,
        }) || ((o = o === null ? Wt.errors : o.concat(Wt.errors)), (s = o.length)),
        (or.errors = o),
        s === 0
      );
    }
    or.evaluated = {
      props: !0,
      dynamicProps: !1,
      dynamicItems: !1,
    };
  })(),
  o = {
    'GET /api/health': {
      200: {
        kind: 'json',
        validate: a.response0,
      },
    },
    'DELETE /api/job-files/{job_file_id}': { 204: { kind: 'empty' } },
    'GET /api/job-files/{job_file_id}': {
      200: {
        kind: 'json',
        validate: a.response2,
      },
    },
    'GET /api/job-files': {
      200: {
        kind: 'json',
        validate: a.response3,
      },
    },
    'POST /api/job-files': {
      200: {
        kind: 'json',
        validate: a.response4,
      },
      201: {
        kind: 'json',
        validate: a.response5,
      },
    },
    'GET /api/job-files/{job_file_id}/interviews': {
      200: {
        kind: 'json',
        validate: a.response6,
      },
    },
    'POST /api/job-files/{job_file_id}/rename': {
      200: {
        kind: 'json',
        validate: a.response7,
      },
    },
    'POST /api/job-files/{job_file_id}/inputs': {
      200: {
        kind: 'json',
        validate: a.response8,
      },
      202: {
        kind: 'json',
        validate: a.response9,
      },
    },
    'GET /api/job-files/{job_file_id}/interview-plan': {
      200: {
        kind: 'json',
        validate: a.response10,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/current': {
      200: {
        kind: 'json',
        validate: a.response11,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}': {
      200: {
        kind: 'json',
        validate: a.response12,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/by-command/{command_id}': {
      200: {
        kind: 'json',
        validate: a.response13,
      },
    },
    'POST /api/job-files/{job_file_id}/consultant-turns/{execution_id}/pause': {
      200: {
        kind: 'json',
        validate: a.response14,
      },
    },
    'POST /api/job-files/{job_file_id}/consultant-turns/{execution_id}/cancel': {
      200: {
        kind: 'json',
        validate: a.response15,
      },
    },
    'POST /api/job-files/{job_file_id}/consultant-turns/{execution_id}/resume': {
      200: {
        kind: 'json',
        validate: a.response16,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}/reasoning-summaries': {
      200: {
        kind: 'json',
        validate: a.response17,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}/activity-stream': {
      200: {
        kind: 'media',
        mediaTypes: ['text/event-stream'],
      },
      204: { kind: 'empty' },
    },
    'GET /api/job-files/{job_file_id}/jd/profile': {
      200: {
        kind: 'json',
        validate: a.response20,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/profile': {
      200: {
        kind: 'json',
        validate: a.response21,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/areas': {
      200: {
        kind: 'json',
        validate: a.response22,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/areas': {
      200: {
        kind: 'json',
        validate: a.response23,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/capabilities': {
      200: {
        kind: 'json',
        validate: a.response24,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/capabilities': {
      200: {
        kind: 'json',
        validate: a.response25,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/collaborators': {
      200: {
        kind: 'json',
        validate: a.response26,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/collaborators': {
      200: {
        kind: 'json',
        validate: a.response27,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/conditions': {
      200: {
        kind: 'json',
        validate: a.response28,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/conditions': {
      200: {
        kind: 'json',
        validate: a.response29,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/tasks': {
      200: {
        kind: 'json',
        validate: a.response30,
      },
    },
    'POST /api/job-files/{job_file_id}/jd/tasks': {
      200: {
        kind: 'json',
        validate: a.response31,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/work': {
      200: {
        kind: 'json',
        validate: a.response32,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/sources': {
      200: {
        kind: 'json',
        validate: a.response33,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/sources/{citation_id}': {
      200: {
        kind: 'json',
        validate: a.response34,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/sources/{citation_id}/changes': {
      200: {
        kind: 'json',
        validate: a.response35,
      },
    },
    'GET /api/job-files/{job_file_id}/jd/export.pdf': {
      200: {
        kind: 'media',
        mediaTypes: ['application/pdf'],
      },
    },
    'POST /api/job-files/{job_file_id}/consultant-turns/{execution_id}/undo-jd': {
      200: {
        kind: 'json',
        validate: a.response37,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}/jd-changes': {
      200: {
        kind: 'json',
        validate: a.response38,
      },
    },
    'GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}/tools': {
      200: {
        kind: 'json',
        validate: a.response39,
      },
    },
    'GET /api/job-files/{job_file_id}/memory': {
      200: {
        kind: 'json',
        validate: a.response40,
      },
    },
    'GET /api/job-files/{job_file_id}/memory/{snapshot_id}/objects/{object_id}': {
      200: {
        kind: 'json',
        validate: a.response41,
      },
    },
  },
  s = a.isAcceptedInterviewInput,
  c = a.isAddDetail,
  l = a.isAllowedControl,
  u = a.isArea,
  d = a.isAreaField,
  f = a.isAreaFieldChange,
  p = a.isCall,
  m = a.isCandidateJdPreview,
  h = a.isCapability,
  g = a.isCapabilityField,
  ee = a.isCapabilityKind,
  te = a.isClearField,
  _ = a.isCollaborator,
  ne = a.isCollaboratorField,
  v = a.isCollaboratorFieldChange,
  y = a.isCommentaryUpdate,
  b = a.isCondition,
  x = a.isConditionKind,
  re = a.isConditionKindChange,
  S = a.isConditionTextChange,
  C = a.isConsultantTurn,
  w = a.isCreateArea,
  T = a.isCreateCapability,
  ie = a.isCreateCollaborator,
  E = a.isCreateCondition,
  D = a.isCreateJobFileRequest,
  O = a.isCreateTask,
  ae = a.isCurrentConsultantTurn,
  oe = a.isDeleteArea,
  se = a.isDeleteCapability,
  ce = a.isDeleteCollaborator,
  le = a.isDeleteCondition,
  ue = a.isDeleteTask,
  k = a.isDetail,
  de = a.isDetailKind,
  fe = a.isDisplayName,
  pe = a.isEditJdAreasRequest,
  me = a.isEditJdCapabilitiesRequest,
  he = a.isEditJdCollaboratorsRequest,
  ge = a.isEditJdConditionsRequest,
  _e = a.isEditJdTasksRequest,
  ve = a.isExecutionStatus,
  A = a.isFieldChange,
  j = a.isHealthStatus,
  ye = a.isHttpErrorDetail,
  be = a.isHttpErrorResponse,
  xe = a.isInterviewContent,
  Se = a.isInterviewHistory,
  Ce = a.isInterviewMessage,
  M = a.isInterviewPlan,
  we = a.isInterviewPlanView,
  Te = a.isInterviewSpeaker,
  N = a.isJdAreasView,
  P = a.isJdCapabilitiesView,
  F = a.isJdCollaboratorsView,
  I = a.isJdConditionsView,
  Ee = a.isJdProfileView,
  L = a.isJdSourceChangesView,
  De = a.isJdSourceContentView,
  R = a.isJdSourcesView,
  Oe = a.isJdTasksView,
  ke = a.isJdWorkView,
  Ae = a.isJobFile,
  je = a.isJobFileList,
  Me = a.isMemoryContent,
  Ne = a.isMemoryLayer,
  Pe = a.isMemoryMapItem,
  Fe = a.isMoveTask,
  Ie = a.isNonblankText,
  z = a.isNonemptyText,
  Le = a.isNonnegativeInteger,
  Re = a.isPositiveInteger,
  ze = a.isProfile,
  B = a.isProfileField,
  Be = a.isPublicCommentary,
  Ve = a.isPublishedMemory,
  He = a.isPublishedMemoryObject,
  Ue = a.isReasoningSummary,
  V = a.isReference,
  We = a.isRemoveDetail,
  Ge = a.isRenameJobFileRequest,
  H = a.isReorderArea,
  Ke = a.isReorderCapability,
  qe = a.isReorderCollaborator,
  Je = a.isReorderCondition,
  Ye = a.isReorderDetail,
  U = a.isReorderTaskCapability,
  W = a.isReviseArea,
  G = a.isReviseCapability,
  K = a.isReviseCollaborator,
  Xe = a.isReviseCondition,
  Ze = a.isReviseDetail,
  Qe = a.isReviseJdProfileRequest,
  $e = a.isReviseTask,
  et = a.isSetTaskCapability,
  tt = a.isSourceLink,
  nt = a.isSourceTargetKind,
  rt = a.isSourceVersion,
  it = a.isSubmitInterviewInput,
  q = a.isTarget,
  at = a.isTaskChange,
  J = a.isTaskField,
  ot = a.isTaskLink,
  st = a.isTurnJdChanges,
  ct = a.isTurnTools,
  lt = a.isWireUuid,
  ut = a.isWorkTask;
export {
  s as isAcceptedInterviewInput,
  c as isAddDetail,
  l as isAllowedControl,
  u as isArea,
  d as isAreaField,
  f as isAreaFieldChange,
  p as isCall,
  m as isCandidateJdPreview,
  h as isCapability,
  g as isCapabilityField,
  ee as isCapabilityKind,
  te as isClearField,
  _ as isCollaborator,
  ne as isCollaboratorField,
  v as isCollaboratorFieldChange,
  y as isCommentaryUpdate,
  b as isCondition,
  x as isConditionKind,
  re as isConditionKindChange,
  S as isConditionTextChange,
  C as isConsultantTurn,
  w as isCreateArea,
  T as isCreateCapability,
  ie as isCreateCollaborator,
  E as isCreateCondition,
  D as isCreateJobFileRequest,
  O as isCreateTask,
  ae as isCurrentConsultantTurn,
  oe as isDeleteArea,
  se as isDeleteCapability,
  ce as isDeleteCollaborator,
  le as isDeleteCondition,
  ue as isDeleteTask,
  k as isDetail,
  de as isDetailKind,
  fe as isDisplayName,
  pe as isEditJdAreasRequest,
  me as isEditJdCapabilitiesRequest,
  he as isEditJdCollaboratorsRequest,
  ge as isEditJdConditionsRequest,
  _e as isEditJdTasksRequest,
  ve as isExecutionStatus,
  A as isFieldChange,
  j as isHealthStatus,
  ye as isHttpErrorDetail,
  be as isHttpErrorResponse,
  xe as isInterviewContent,
  Se as isInterviewHistory,
  Ce as isInterviewMessage,
  M as isInterviewPlan,
  we as isInterviewPlanView,
  Te as isInterviewSpeaker,
  N as isJdAreasView,
  P as isJdCapabilitiesView,
  F as isJdCollaboratorsView,
  I as isJdConditionsView,
  Ee as isJdProfileView,
  L as isJdSourceChangesView,
  De as isJdSourceContentView,
  R as isJdSourcesView,
  Oe as isJdTasksView,
  ke as isJdWorkView,
  Ae as isJobFile,
  je as isJobFileList,
  Me as isMemoryContent,
  Ne as isMemoryLayer,
  Pe as isMemoryMapItem,
  Fe as isMoveTask,
  Ie as isNonblankText,
  z as isNonemptyText,
  Le as isNonnegativeInteger,
  Re as isPositiveInteger,
  ze as isProfile,
  B as isProfileField,
  Be as isPublicCommentary,
  Ve as isPublishedMemory,
  He as isPublishedMemoryObject,
  Ue as isReasoningSummary,
  V as isReference,
  We as isRemoveDetail,
  Ge as isRenameJobFileRequest,
  H as isReorderArea,
  Ke as isReorderCapability,
  qe as isReorderCollaborator,
  Je as isReorderCondition,
  Ye as isReorderDetail,
  U as isReorderTaskCapability,
  W as isReviseArea,
  G as isReviseCapability,
  K as isReviseCollaborator,
  Xe as isReviseCondition,
  Ze as isReviseDetail,
  Qe as isReviseJdProfileRequest,
  $e as isReviseTask,
  et as isSetTaskCapability,
  tt as isSourceLink,
  nt as isSourceTargetKind,
  rt as isSourceVersion,
  it as isSubmitInterviewInput,
  q as isTarget,
  at as isTaskChange,
  J as isTaskField,
  ot as isTaskLink,
  st as isTurnJdChanges,
  ct as isTurnTools,
  lt as isWireUuid,
  ut as isWorkTask,
  o as responsePolicies,
};
