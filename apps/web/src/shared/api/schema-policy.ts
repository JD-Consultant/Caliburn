/** One wire admission policy; each feature registers and compiles its own schemas. */
import { Ajv2020 } from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import { canonicalUuid } from './uuid';

export function createSchemaValidator(): Ajv2020 {
  const validator = new Ajv2020();
  addFormats(validator);
  // JSON Schema 2020-12 §7.3.5 uses plain UUIDs; ajv-formats also accepts URNs.
  validator.addFormat('uuid', {
    type: 'string',
    validate: (value) => canonicalUuid(value) !== null,
  });
  return validator;
}
