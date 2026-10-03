/* Generated from apps/api/contracts; do not edit. */

/**
 * Read selected formal historical interview messages, not current input or instructions. The App binds the job file, source eligibility and read upper bound. An unavailable or out-of-scope sequence rejects the whole query; incomplete reads are not silently truncated.
 */
export interface ReadInterviewArguments {
  /**
   * Choose explicit messages or an inclusive range using formal interview sequences; smaller numbers mean earlier speech within the same job file.
   */
  query: InterviewMessagesQuery | InterviewRangeQuery;
}
export interface InterviewMessagesQuery {
  kind: 'messages';
  /**
   * Select one or more formal sequences; gaps and duplicates are allowed. The domain deduplicates and returns only selected messages in ascending order, without renumbering or adding context.
   *
   * @minItems 1
   */
  sequences: [number, ...number[]];
}
export interface InterviewRangeQuery {
  kind: 'range';
  /**
   * First included formal sequence. Must not exceed end_sequence; the domain validates the ordering.
   */
  start_sequence: number;
  /**
   * Last included formal sequence. Return every eligible message in the closed interval, subject to the App-bound scope.
   */
  end_sequence: number;
}
