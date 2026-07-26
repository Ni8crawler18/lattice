"use client";

/* Standalone route for the Group-by-DIGIPIN overlay (Xenon): /map
   The same component also renders as the console's "Group by DIGIPIN" tab. */

import Link from "next/link";
import GroupByDigipin from "./GroupByDigipin";

export default function MapPage() {
  return (
    <div style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px 60px" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 22, margin: 0 }}>Group by DIGIPIN</h1>
        <Link href="/dashboard" style={{ fontSize: 13, opacity: 0.7, textDecoration: "none" }}>
          &larr; console
        </Link>
      </header>
      <GroupByDigipin />
    </div>
  );
}
