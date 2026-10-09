import type { Translate } from "../../i18n/LanguageProvider";
import type { MessageKey } from "../../i18n/en";
import type { TargetJob } from "../../types/api";

const STAGE_KEYS: Record<string, MessageKey> = {
  not_applied: "targets.stage.notApplied",
  submitted: "targets.stage.submitted",
  written_test: "targets.stage.writtenTest",
  interview_1: "targets.stage.interview1",
  interview_2: "targets.stage.interview2",
  hr_interview: "targets.stage.hrInterview",
  offer: "targets.stage.offer",
  rejected: "targets.stage.rejected",
};

// 未知阶段原样显示，避免后端新增阶段时页面空白
export function stageLabel(stage: string, t: Translate) {
  const key = STAGE_KEYS[stage];
  return key ? t(key) : stage;
}

// 四步准备进度：JD 已匹配（加入目标即完成）、简历已改写、模拟面试已完成、已投递
export function completedSteps(target: TargetJob) {
  return 1
    + (target.rewrite_status !== "none" ? 1 : 0)
    + (target.interview_done_at ? 1 : 0)
    + (target.stage !== "not_applied" ? 1 : 0);
}

export function averageProgress(targets: TargetJob[]) {
  if (!targets.length) return 0;
  return Math.round(targets.reduce((total, target) => total + completedSteps(target) * 25, 0) / targets.length);
}
