import { StrictMode } from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { startActivityCapture } from "./activity";

startActivityCapture();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
