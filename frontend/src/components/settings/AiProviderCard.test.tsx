import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AiProviderCard } from "./AiProviderCard";
import type { SettingsState } from "../../hooks/useSettings";

const baseSettings: SettingsState = {
  update_hour: 22,
  update_minute: 30,
  update_weekends: false,
  ai_provider: "openai",
  ai_endpoint: null,
  ai_model: "gpt-4o-mini",
  ai_refresh_interval: "monthly",
  ai_api_key_set: true,
  jobs_enabled: true,
  jobs_update_hour: 2,
  jobs_update_minute: 0,
};

function makeProps(overrides: Partial<Parameters<typeof AiProviderCard>[0]> = {}) {
  return {
    settings: baseSettings,
    onChange: vi.fn(),
    apiKey: "",
    setApiKey: vi.fn(),
    editKey: false,
    setEditKey: vi.fn(),
    testing: false,
    testResult: null,
    setTestResult: vi.fn(),
    isDirty: false,
    onTestConnection: vi.fn(),
    ...overrides,
  };
}

describe("AiProviderCard", () => {
  it("renders the provider select with current value", () => {
    render(<AiProviderCard {...makeProps()} />);
    const select = screen.getByLabelText(/ki-anbieter/i) as HTMLSelectElement;
    expect(select.value).toBe("openai");
  });

  it("renders the model select for presets providers", () => {
    render(<AiProviderCard {...makeProps()} />);
    expect(screen.getByLabelText(/modell/i)).toBeInTheDocument();
  });

  it("shows 'Schlüssel hinterlegt' pill when key is set and not editing", () => {
    render(<AiProviderCard {...makeProps()} />);
    expect(screen.getByText("Schlüssel hinterlegt")).toBeInTheDocument();
  });

  it("calls setEditKey when 'Schlüssel ändern' is clicked", () => {
    const setEditKey = vi.fn();
    render(<AiProviderCard {...makeProps({ setEditKey })} />);
    fireEvent.click(screen.getByRole("button", { name: /schlüssel ändern/i }));
    expect(setEditKey).toHaveBeenCalledWith(true);
  });

  it("shows test button", () => {
    render(<AiProviderCard {...makeProps()} />);
    expect(screen.getByRole("button", { name: /verbindung testen/i })).toBeInTheDocument();
  });

  it("shows 'Kein API-Schlüssel nötig' for ollama", () => {
    render(
      <AiProviderCard
        {...makeProps({
          settings: { ...baseSettings, ai_provider: "ollama", ai_api_key_set: false },
        })}
      />
    );
    expect(screen.getByText(/lokales modell/i)).toBeInTheDocument();
  });

  it("calls onTestConnection when test button is clicked", () => {
    const onTestConnection = vi.fn();
    render(<AiProviderCard {...makeProps({ onTestConnection })} />);
    fireEvent.click(screen.getByRole("button", { name: /verbindung testen/i }));
    expect(onTestConnection).toHaveBeenCalledOnce();
  });
});
