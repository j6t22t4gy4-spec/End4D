"use client";

type TimelineMarker = {
  key: string;
  t: number;
  label: string;
  kind: "frame" | "inject" | "bookmark";
};

type TimelineBookmarksProps = {
  t: number;
  tMin: number;
  tMax: number;
  markers: TimelineMarker[];
  bookmarks: TimelineMarker[];
  onJump: (t: number) => void;
  onAddBookmark: () => void;
  onRemoveBookmark: (key: string) => void;
};

export function TimelineBookmarks({
  t,
  tMin,
  tMax,
  markers,
  bookmarks,
  onJump,
  onAddBookmark,
  onRemoveBookmark,
}: TimelineBookmarksProps) {
  const span = Math.max(1, tMax - tMin);

  return (
    <div className="timeline-bookmarks">
      <div className="timeline-bookmarks__rail">
        {markers.map((marker) => {
          const left = `${((marker.t - tMin) / span) * 100}%`;
          return (
            <button
              key={marker.key}
              type="button"
              className={`timeline-bookmarks__marker timeline-bookmarks__marker--${marker.kind}`}
              style={{ left }}
              onClick={() => onJump(marker.t)}
              title={`${marker.label} · t=${marker.t}`}
            />
          );
        })}
        <div
          className="timeline-bookmarks__cursor"
          style={{ left: `${((t - tMin) / span) * 100}%` }}
        />
      </div>

      <div className="timeline-bookmarks__actions">
        <button
          type="button"
          className="app-button app-button--secondary"
          onClick={onAddBookmark}
        >
          Bookmark current t
        </button>
        <span className="text-xs text-slate-500">
          inject / bookmark / frame markers
        </span>
      </div>

      {bookmarks.length > 0 ? (
        <div className="timeline-bookmarks__chips">
          {bookmarks.map((bookmark) => (
            <div key={bookmark.key} className="timeline-bookmarks__chip">
              <button type="button" onClick={() => onJump(bookmark.t)}>
                {bookmark.label}
              </button>
              <button
                type="button"
                className="timeline-bookmarks__chip-remove"
                onClick={() => onRemoveBookmark(bookmark.key)}
                aria-label={`Remove ${bookmark.label}`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export type { TimelineMarker };
