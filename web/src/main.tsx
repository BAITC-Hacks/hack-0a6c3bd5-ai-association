import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/onest";
import "@fontsource-variable/unbounded";
import "@fontsource/ibm-plex-mono/cyrillic-400.css";
import "@fontsource/ibm-plex-mono/cyrillic-500.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import App from "./App";
import "./styles.css";
import "./catalog.css";
import "./commerce.css";
import "./checkout.css";
import "./upload.css";
import "./kontur.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
