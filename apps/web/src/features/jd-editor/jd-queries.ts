import type { QueryFilters } from '@tanstack/react-query';
import { jdProfileQuery } from './jd-profile-api';
import { jdWorkQuery } from './jd-work-api';

/** Profile and collections share one formal revision. */
export function formalJdQueries(jobFileId: string): readonly QueryFilters[] {
  return [
    { queryKey: jdProfileQuery(jobFileId).queryKey, exact: true },
    { queryKey: jdWorkQuery(jobFileId).queryKey, exact: true },
  ];
}
