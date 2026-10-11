"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface UsePollingResult<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  shouldStop?: (data: T | null) => boolean
): UsePollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetcherRef = useRef(fetcher);
  const shouldStopRef = useRef(shouldStop);

  useEffect(() => {
    fetcherRef.current = fetcher;
    shouldStopRef.current = shouldStop;
  });

  const inFlightRef = useRef(false);
  const stoppedRef = useRef(false);
  const timeoutIdRef = useRef<NodeJS.Timeout | null>(null);

  const execute = useCallback(async () => {
    if (inFlightRef.current || stoppedRef.current) return;
    inFlightRef.current = true;

    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      if (shouldStopRef.current && shouldStopRef.current(result)) {
        stoppedRef.current = true;
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      inFlightRef.current = false;
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    stoppedRef.current = false;
    await execute();
  }, [execute]);

  useEffect(() => {
    stoppedRef.current = false;
    let isMounted = true;

    const pollLoop = async () => {
      if (!isMounted) return;
      await execute();
      if (!isMounted || stoppedRef.current) return;

      timeoutIdRef.current = setTimeout(pollLoop, intervalMs);
    };

    pollLoop();

    return () => {
      isMounted = false;
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
      }
    };
  }, [execute, intervalMs]);

  return { data, error, loading, refresh };
}
