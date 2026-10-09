import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApiError } from "../../api";
import { resumesApi } from "../../api/resumes";
import { targetsApi } from "../../api/targets";
import type { ResumeRewriteResult, RewriteBlock, RewriteSession as StoredSession, SavedResumeRewrite, TargetJob, UserInputRequest } from "../../types/api";
import { blockKey, buildFinalResume, draftKey, type Review } from "./assemble";

// 错误一律保存原始 reason，由页面按当前语言转成文案
type Failure = { reason: unknown };

// 待补充块里带问询的那条改动（只有文本字段会带占位）
export const inputChangeIndex = (block: RewriteBlock) => block.changes.findIndex((change) => change.needs_user_input.length > 0);

// 改写对比和审阅进度自动保存到后端的防抖间隔
const AUTOSAVE_MS = 800;

// 简历改写页的状态与接口调用：目标岗位、已保存的对比与终稿、生成改写、补充问询、审阅、保存
export function useRewriteSession() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [targets, setTargets] = useState<TargetJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState<SavedResumeRewrite | null>(null);
  const [result, setResult] = useState<ResumeRewriteResult | null>(null);
  const [generating, setGenerating] = useState(false);
  const [filling, setFilling] = useState(false);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  // 当前对比是从数据库恢复的（而不是刚生成的）
  const [restored, setRestored] = useState(false);
  const [active, setActive] = useState(0);
  const [reviews, setReviews] = useState<Record<string, Review>>({});
  // 每条文本改动的当前草稿（用户编辑或补全后的值），key 见 draftKey
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  // 每个待补充块还没回答的问询
  const [pending, setPending] = useState<Record<string, UserInputRequest[]>>({});
  // 问询输入框的内容，key 为 `${blockKey}|${placeholder}`
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [confirmedDeletions, setConfirmedDeletions] = useState<Record<number, boolean>>({});
  const [error, setError] = useState<Failure | null>(null);

  // 优先用 URL 里的 ?job=（从目标岗位卡片跳转过来），不是目标岗位时退回第一个
  const requestedJobId = Number(searchParams.get("job"));
  const selectedTarget = targets.find((target) => target.job_id === requestedJobId) ?? targets[0] ?? null;
  const selectedJobId = selectedTarget?.job_id ?? null;
  const blocks = result?.blocks ?? [];
  const block = blocks[active] ?? null;
  const reviewable = blocks.filter((item) => item.status !== "unchanged");
  const reviewedCount = reviewable.filter((item) => reviews[blockKey(item)]).length;
  const acceptedCount = reviewable.filter((item) => reviews[blockKey(item)] === "accepted").length;

  useEffect(() => {
    let activeRequest = true;
    targetsApi.list()
      .then((items) => { if (activeRequest) setTargets(items); })
      .catch((reason) => activeRequest && setError({ reason }))
      .finally(() => activeRequest && setLoading(false));
    return () => { activeRequest = false; };
  }, []);

  // 载入一份改写对比：先按改写结果生成初始草稿/问询，再用已保存的审阅进度覆盖
  const hydrate = (next: ResumeRewriteResult, stored?: StoredSession) => {
    const nextDrafts: Record<string, string> = {};
    const nextPending: Record<string, UserInputRequest[]> = {};
    for (const item of next.blocks) {
      item.changes.forEach((change, index) => { if (typeof change.value === "string") nextDrafts[draftKey(item, index)] = change.value; });
      if (item.status === "needs_input") nextPending[blockKey(item)] = item.pending_inputs;
    }
    setResult(next);
    setDrafts({ ...nextDrafts, ...stored?.drafts });
    setPending({ ...nextPending, ...stored?.pending });
    setReviews(stored?.reviews ?? {}); setAnswers({}); setConfirmedDeletions(stored?.confirmed_deletions ?? {});
    // 默认打开第一个需要审阅的块
    setActive(Math.max(0, next.blocks.findIndex((item) => item.status !== "unchanged")));
  };

  // 切换岗位：清空上一个岗位的改写结果，读该岗位已保存的对比和终稿（不调用大模型）
  useEffect(() => {
    setResult(null); setSaved(null); setError(null); setJustSaved(false); setRestored(false);
    if (!selectedJobId) return;
    let activeRequest = true;
    resumesApi.getSavedRewrite(selectedJobId)
      .then((item) => {
        if (!activeRequest) return;
        setSaved(item);
        if (item.session) { hydrate(item.session.result, item.session); setRestored(true); }
      })
      .catch((reason) => {
        // 404 = 这个岗位还没保存过终稿
        if (activeRequest && !(reason instanceof ApiError && reason.status === 404)) setError({ reason });
      });
    return () => { activeRequest = false; };
  }, [selectedJobId]);

  const currentSession = (): StoredSession | null => result && { result, reviews, drafts, pending, confirmed_deletions: confirmedDeletions };

  // 审阅进度有变化就防抖保存；切换岗位时 cleanup 取消未发出的保存，不会存到别的岗位下
  useEffect(() => {
    const session = currentSession();
    if (!selectedJobId || !session) return;
    const timer = setTimeout(() => { resumesApi.saveRewriteSession(selectedJobId, session).catch((reason) => setError({ reason })); }, AUTOSAVE_MS);
    return () => clearTimeout(timer);
  }, [selectedJobId, result, reviews, drafts, pending, confirmedDeletions]);

  const selectJob = (jobId: number) => setSearchParams({ job: String(jobId) });

  const generate = async () => {
    if (!selectedJobId) return;
    setGenerating(true); setError(null); setJustSaved(false);
    try {
      // 后端生成后已把结果存为该岗位的改写对比
      hydrate(await resumesApi.generateRewrite(selectedJobId));
      setRestored(false);
    } catch (reason) { setError({ reason }); }
    finally { setGenerating(false); }
  };

  const editDraft = (target: RewriteBlock, changeIndex: number, value: string) =>
    setDrafts((current) => ({ ...current, [draftKey(target, changeIndex)]: value }));

  const setAnswer = (target: RewriteBlock, placeholder: string, value: string) =>
    setAnswers((current) => ({ ...current, [`${blockKey(target)}|${placeholder}`]: value }));

  const answerOf = (target: RewriteBlock, placeholder: string) => answers[`${blockKey(target)}|${placeholder}`] ?? "";

  // 提交本块所有问询：留空的题按「跳过」处理（answer 为 null，大模型改成中性表述）
  const submitAnswers = async (target: RewriteBlock) => {
    const changeIndex = inputChangeIndex(target);
    const questions = pending[blockKey(target)] ?? [];
    if (!selectedJobId || changeIndex < 0 || target.section === "skills" || !questions.length) return;
    setFilling(true); setError(null);
    try {
      const filled = await resumesApi.fillRewriteBlock({
        job_id: selectedJobId,
        section: target.section,
        index: target.index,
        text: drafts[draftKey(target, changeIndex)],
        answers: questions.map((question) => ({ placeholder: question.placeholder, answer: answerOf(target, question.placeholder).trim() || null })),
      });
      editDraft(target, changeIndex, filled.value);
      setPending((current) => ({ ...current, [blockKey(target)]: filled.needs_user_input }));
      setAnswers((current) => Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(`${blockKey(target)}|`))));
    } catch (reason) { setError({ reason }); }
    finally { setFilling(false); }
  };

  const review = (target: RewriteBlock, value: Review) => setReviews((current) => ({ ...current, [blockKey(target)]: value }));

  const toggleDeletion = (index: number) => setConfirmedDeletions((current) => ({ ...current, [index]: !current[index] }));

  // 按当前审阅状态组装的终稿；还没有对比时用已保存的终稿（导出 PDF 用）
  const finalResume = () => result
    ? buildFinalResume(result, reviews, drafts, result.deletion_suggestions.filter((_, index) => confirmedDeletions[index]))
    : saved?.resume ?? null;

  const save = async () => {
    const session = currentSession();
    if (!selectedJobId || !session) return;
    setSaving(true); setError(null);
    try {
      // 先把最新进度落库，防抖还没触发时也不会丢
      await resumesApi.saveRewriteSession(selectedJobId, session);
      const next = await resumesApi.saveRewrite(selectedJobId, finalResume()!);
      setSaved({ ...next, session });
      setJustSaved(true);
    } catch (reason) { setError({ reason }); }
    finally { setSaving(false); }
  };

  return {
    targets, loading, selectedTarget, selectJob,
    saved, justSaved, restored, result, finalResume, generating, generate,
    blocks, block, active, setActive, reviews, review, reviewable, reviewedCount, acceptedCount,
    drafts, editDraft, pending, answerOf, setAnswer, filling, submitAnswers,
    confirmedDeletions, toggleDeletion, saving, save, error,
    canSave: Boolean(result) && reviewedCount === reviewable.length,
  };
}

export type RewriteSession = ReturnType<typeof useRewriteSession>;
