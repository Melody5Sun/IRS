import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./app/App";
import { LanguageProvider } from "./i18n/LanguageProvider";
// 样式按原单文件中的层叠顺序引入，调整顺序可能改变覆盖结果
import "./styles/tokens.css";
import "./styles/base.css";
import "./components/layout/layout.css";
import "./features/dashboard/dashboard.css";
import "./features/profile/profile.css";
import "./features/jobs/jobs.css";
import "./features/rewrite/rewrite.css";
import "./features/interview/interview.css";
import "./features/targets/targets.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>,
);
