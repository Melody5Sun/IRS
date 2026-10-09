import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import type { MessageKey } from "../i18n/en";
import type { Page } from "../types/domain";

type RouteMeta = {
  path: string;
  // 面包屑文案；仪表盘没有面包屑
  crumbKey: MessageKey | null;
  hideFooter?: boolean;
};

// 参考原型 FLOW 的五步流程，所有页面的路径和元信息只在这里定义一次
export const ROUTES: Record<Page, RouteMeta> = {
  dashboard: { path: "/", crumbKey: null },
  profile: { path: "/profile", crumbKey: "nav.profile" },
  jobs: { path: "/jobs", crumbKey: "nav.jobs", hideFooter: true },
  rewrite: { path: "/rewrite", crumbKey: "nav.rewrite" },
  interview: { path: "/interview", crumbKey: "nav.interview" },
  targets: { path: "/targets", crumbKey: "nav.targets", hideFooter: true },
};

const PAGES = Object.keys(ROUTES) as Page[];

export function pageFromPath(pathname: string): Page | null {
  return PAGES.find((page) => ROUTES[page].path === pathname) ?? null;
}

// 旧版用 #jobs 这类 hash 路由，保留对旧书签的识别
export function pageFromLegacyHash(hash: string): Page | null {
  const value = hash.slice(1) as Page;
  return PAGES.includes(value) ? value : null;
}

export function useGo() {
  const navigate = useNavigate();
  return useCallback((page: Page) => navigate(ROUTES[page].path), [navigate]);
}
