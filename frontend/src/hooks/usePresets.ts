import { useEffect, useState } from "react";
import { emptyFilters, FilterValues } from "./useWatchlistFilters";
import { confirm, prompt } from "../lib/dialogs";

interface UsePresetsOptions {
  filterValues: FilterValues;
  onApply: (values: FilterValues) => void;
}

export function usePresets({ filterValues, onApply }: UsePresetsOptions) {
  const [savedPresets, setSavedPresets] = useState<Record<string, FilterValues>>({});

  useEffect(() => {
    const raw = localStorage.getItem("ct-presets");
    if (!raw) return;
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSavedPresets(JSON.parse(raw));
    } catch {
      // ignore corrupt data
    }
  }, []);

  function persistPresets(next: Record<string, FilterValues>) {
    setSavedPresets(next);
    localStorage.setItem("ct-presets", JSON.stringify(next));
  }

  async function savePresetPrompt() {
    const name = await prompt({
      title: "Voreinstellung speichern",
      message: "Wie soll die Voreinstellung heißen?",
      placeholder: "z. B. Dividendenfokus",
      confirmLabel: "Speichern",
      validate: (value) => (value.trim() ? null : "Bitte einen Namen eingeben."),
    });
    if (!name) return;
    const trimmed = name.trim();
    if (!trimmed) return;
    if (savedPresets[trimmed]) {
      const overwrite = await confirm({
        title: "Voreinstellung überschreiben",
        message: `Voreinstellung "${trimmed}" überschreiben?`,
      });
      if (!overwrite) return;
    }
    persistPresets({ ...savedPresets, [trimmed]: filterValues });
  }

  function applyPreset(name: string) {
    const p = savedPresets[name];
    if (!p) return;
    onApply({ ...emptyFilters, ...p });
  }

  async function deletePreset(name: string) {
    const confirmed = await confirm({
      title: "Voreinstellung löschen",
      message: `Voreinstellung "${name}" wirklich löschen?`,
      destructive: true,
    });
    if (!confirmed) return;
    const next = { ...savedPresets };
    delete next[name];
    persistPresets(next);
  }

  return {
    savedPresets,
    presetNames: Object.keys(savedPresets),
    savePresetPrompt,
    applyPreset,
    deletePreset,
  };
}
