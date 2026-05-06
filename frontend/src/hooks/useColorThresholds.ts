import { useEffect, useState } from "react";
import { ColorThresholds, defaultThresholds } from "../lib/colorRules";

export function useColorThresholds(): ColorThresholds {
  const [thresholds, setThresholds] = useState<ColorThresholds>(defaultThresholds);

  useEffect(() => {
    const raw = localStorage.getItem("ct-thresholds");
    if (!raw) return;
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setThresholds({ ...defaultThresholds, ...JSON.parse(raw) });
    } catch {
      // ignore corrupt data
    }
  }, []);

  return thresholds;
}
