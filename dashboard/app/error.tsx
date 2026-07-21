"use client";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="app-container">
      <main className="main-content" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "60vh", gap: 16 }}>
        <div style={{ fontSize: 48, opacity: 0.5 }}>⚠</div>
        <h2 style={{ color: "var(--red)", fontSize: 20 }}>Dashboard Error</h2>
        <p style={{ color: "var(--text-muted)", maxWidth: 400, textAlign: "center" }}>
          {error.message || "Terjadi kesalahan yang tidak terduga."}
        </p>
        <button
          className="btn btn-primary"
          onClick={() => reset()}
          style={{ marginTop: 8 }}
        >
          Coba Lagi
        </button>
      </main>
    </div>
  );
}
