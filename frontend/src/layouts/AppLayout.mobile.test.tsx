import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock useAuth to avoid API calls
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({ user: { username: "testuser", role: "admin" }, loading: false }),
}));

// Mock useCurrentRun to return idle state
vi.mock("../lib/runProgress", () => ({
  useCurrentRun: () => ({ data: null }),
}));

// Mock useBreakpoint to control mobile/desktop rendering
const mockIsMobile = { value: true };
vi.mock("../hooks/useBreakpoint", () => ({
  useBreakpoint: () => (mockIsMobile.value ? "mobile" : "desktop"),
  useIsMobile: () => mockIsMobile.value,
}));

import { AppLayout } from "./AppLayout";

function renderLayout() {
  return render(
    <MemoryRouter>
      <AppLayout>
        <div>Page Content</div>
      </AppLayout>
    </MemoryRouter>
  );
}

describe("AppLayout — mobile", () => {
  beforeEach(() => {
    mockIsMobile.value = true;
  });

  it("renders the MobileTopBar on mobile", () => {
    renderLayout();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /navigation öffnen/i })).toBeInTheDocument();
  });

  it("does not render desktop nav on mobile", () => {
    renderLayout();
    // Desktop nav links should not be present (only bottom-tab links exist)
    // The bottom tabs render Dashboard, Watchlist, Stellen, Läufe
    expect(screen.queryByText("Einstellungen")).not.toBeInTheDocument();
  });

  it("renders bottom-tab navigation", () => {
    renderLayout();
    expect(screen.getByRole("navigation", { name: /hauptnavigation/i })).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Watchlist")).toBeInTheDocument();
    expect(screen.getByText("Stellen")).toBeInTheDocument();
    expect(screen.getByText("Läufe")).toBeInTheDocument();
  });

  it("opens the drawer when the hamburger button is clicked", () => {
    renderLayout();
    const hamburger = screen.getByRole("button", { name: /navigation öffnen/i });
    fireEvent.click(hamburger);
    expect(screen.getByRole("dialog", { name: /navigation/i })).toBeInTheDocument();
  });

  it("shows Einstellungen link inside the drawer", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: /navigation öffnen/i }));
    expect(screen.getByRole("link", { name: /einstellungen/i })).toBeInTheDocument();
  });

  it("closes the drawer when the close button is clicked", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: /navigation öffnen/i }));
    expect(screen.getByRole("dialog", { name: /navigation/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /navigation schließen/i }));
    expect(screen.queryByRole("dialog", { name: /navigation/i })).not.toBeInTheDocument();
  });

  it("closes the drawer when Escape is pressed", () => {
    renderLayout();
    fireEvent.click(screen.getByRole("button", { name: /navigation öffnen/i }));
    expect(screen.getByRole("dialog", { name: /navigation/i })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: /navigation/i })).not.toBeInTheDocument();
  });
});

describe("AppLayout — desktop", () => {
  beforeEach(() => {
    mockIsMobile.value = false;
  });

  it("renders desktop nav on desktop", () => {
    renderLayout();
    expect(screen.getByText("Einstellungen")).toBeInTheDocument();
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("does not render mobile top-bar on desktop", () => {
    renderLayout();
    expect(screen.queryByRole("button", { name: /navigation öffnen/i })).not.toBeInTheDocument();
  });
});
