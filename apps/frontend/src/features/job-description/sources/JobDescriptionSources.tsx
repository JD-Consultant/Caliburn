import { Button } from '@mui/material';
import { useContext } from 'react';
import { SourcesContext } from './sources-context';

export function JobDescriptionSources() {
  const sources = useContext(SourcesContext);
  if (!sources) return null;
  return (
    <Button
      size="small"
      variant="outlined"
      aria-expanded={sources.open}
      onClick={(event) => sources.show(event.currentTarget)}
    >
      JD 來源（唯讀）
    </Button>
  );
}
