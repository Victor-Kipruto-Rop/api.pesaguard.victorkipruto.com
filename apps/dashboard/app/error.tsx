"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) { return <main className="error-screen"><p className="eyebrow">Application error</p><h1>Unable to load this view</h1><button className="button primary" onClick={reset}>Try again</button></main>; }
