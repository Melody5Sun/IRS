import type { ReactNode } from "react";

// 模态对话框外壳：遮罩 + 卡片；标题元素需带 titleId 对应的 id
export function Dialog({ titleId, className, children }: { titleId: string; className?: string; children: ReactNode }) {
  return (
    <div className="dialog-backdrop">
      <div className={className ? `profile-dialog ${className}` : "profile-dialog"} role="dialog" aria-modal="true" aria-labelledby={titleId}>
        {children}
      </div>
    </div>
  );
}
