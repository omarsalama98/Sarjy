/**
 * Sarjy. One screen.
 *
 * The user must always know which state they are in: idle, listening, thinking,
 * speaking. State changes render IMMEDIATELY even when the response does not —
 * the cheapest perceived-latency win available, and it costs nothing.
 */

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
