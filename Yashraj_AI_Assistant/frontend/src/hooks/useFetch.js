import { useCallback, useEffect, useState } from "react";

export default function useFetch(fetcher, deps = [], immediate = true) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(immediate);
  const [error, setError] = useState("");

  const refetch = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await fetcher();
      setData(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch";
      setError(message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, deps);

  useEffect(() => {
    if (!immediate) return;
    refetch().catch(() => {});
  }, [immediate, refetch]);

  return { data, setData, loading, error, refetch };
}
