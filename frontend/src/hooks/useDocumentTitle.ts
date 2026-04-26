import { useEffect } from "react";

const APP_NAME = "CompanyTracker";

/** Sets `document.title` while the calling component is mounted and restores
 *  the previous title on unmount.
 *
 *  Pass `null`/`undefined` to skip (useful while data is still loading) so the
 *  previous page's title doesn't get overwritten with a stale "Lade…" string.
 *  The app name is appended automatically as a suffix.
 */
export function useDocumentTitle(title: string | null | undefined): void {
  useEffect(() => {
    if (!title) return;
    const previous = document.title;
    document.title = `${title} · ${APP_NAME}`;
    return () => {
      document.title = previous;
    };
  }, [title]);
}
