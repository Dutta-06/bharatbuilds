import React from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/latin-400.css";
import "@fontsource/ibm-plex-sans/latin-500.css";
import "@fontsource/ibm-plex-sans/latin-600.css";
import "@fontsource/ibm-plex-mono/latin-400.css";
import "@fontsource/ibm-plex-mono/latin-500.css";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import App from "./App.jsx";
import { applyTheme, getTheme } from "./theme.js";

applyTheme(getTheme());   // before first paint, so a saved choice never flashes the other theme
createRoot(document.getElementById("root")).render(<App />);
