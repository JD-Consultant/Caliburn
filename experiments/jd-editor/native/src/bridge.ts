import { transform } from "./transform.js";
import { validateJdValue } from "./validate.js";
import { readJdSelection } from "./read-selection.js";
import { assertContract, failure, JdInputError } from "./schema.js";
const entries = {
  transform: { run: transform, result: "JdPlateTransformResult" },
  "validate-value": {
    run: validateJdValue,
    result: "JdPlateValidateValueResult",
  },
  "read-selection": {
    run: readJdSelection,
    result: "JdPlateReadSelectionResult",
  },
};
let output: unknown;
try {
  const entry = entries[process.argv[2] as keyof typeof entries];
  if (!entry || process.argv.length !== 3)
    throw new JdInputError("invalid_input", "Unsupported fixed entrypoint.");
  let input = "";
  for await (const chunk of process.stdin) {
    input += chunk;
    if (input.length > 16 * 1024 * 1024)
      throw new JdInputError(
        "invalid_input",
        "Input exceeds the local bridge limit.",
      );
  }
  let request;
  try {
    request = JSON.parse(input);
  } catch {
    throw new JdInputError("invalid_input", "Expected one JSON request.");
  }
  output = entry.run(request);
  assertContract(entry.result, output);
} catch (e) {
  output = failure(e);
}
process.stdout.write(JSON.stringify(output) + "\n");
