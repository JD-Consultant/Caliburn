/** Counts active time while this tab has the job file's workspace open; the server owns the total. */
import { useEffect, useRef, useState } from 'react';
import { recordUsageHeartbeat } from './job-file-api';

const TICK_MS = 1_000;
const HEARTBEAT_MS = 15_000;
const MAX_HEARTBEAT_SECONDS = 60;

export function useUsageTimer(jobFileId: string, baseSeconds: number): number {
  const baseRef = useRef(baseSeconds);
  const [syncedBaseSeconds, setSyncedBaseSeconds] = useState(baseSeconds);
  const [displaySeconds, setDisplaySeconds] = useState(baseSeconds);
  if (baseSeconds !== syncedBaseSeconds) {
    setSyncedBaseSeconds(baseSeconds);
    setDisplaySeconds(baseSeconds);
  }

  useEffect(() => {
    baseRef.current = baseSeconds;
  }, [baseSeconds]);

  useEffect(() => {
    let windowStart = Date.now();

    function elapsedInWindow(): number {
      return Math.min(Math.floor((Date.now() - windowStart) / 1000), MAX_HEARTBEAT_SECONDS);
    }

    function sendHeartbeat(elapsedSeconds: number): void {
      if (elapsedSeconds < 1) return;
      windowStart = Date.now();
      void recordUsageHeartbeat(jobFileId, elapsedSeconds)
        .then((file) => {
          baseRef.current = file.active_usage_seconds;
          setDisplaySeconds(file.active_usage_seconds);
        })
        .catch(() => {
          // Best effort: the next window starts fresh rather than retrying this slice forever.
        });
    }

    function flushViaBeacon(): void {
      const elapsedSeconds = elapsedInWindow();
      if (elapsedSeconds < 1) return;
      const body = new Blob([JSON.stringify({ elapsed_seconds: elapsedSeconds })], {
        type: 'application/json',
      });
      if (navigator.sendBeacon(`/api/job-files/${jobFileId}/usage-heartbeat`, body)) {
        windowStart = Date.now();
      }
    }

    const tick = setInterval(() => {
      setDisplaySeconds(baseRef.current + elapsedInWindow());
    }, TICK_MS);

    const heartbeat = setInterval(() => {
      sendHeartbeat(elapsedInWindow());
    }, HEARTBEAT_MS);

    window.addEventListener('pagehide', flushViaBeacon);
    return () => {
      clearInterval(tick);
      clearInterval(heartbeat);
      window.removeEventListener('pagehide', flushViaBeacon);
      sendHeartbeat(elapsedInWindow());
    };
  }, [jobFileId]);

  return displaySeconds;
}
