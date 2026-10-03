// The Python orchestrator checks/writes both outputs; this is the stock TS generator.
import { compileFromFile } from 'json-schema-to-typescript';

process.stdout.write(
  await compileFromFile(process.argv[2], {
    bannerComment: '/* Generated from apps/api/contracts; do not edit. */',
    style: { singleQuote: true, printWidth: 100 },
  }),
);
