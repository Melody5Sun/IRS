import { useI18n } from "../../i18n/LanguageProvider";
import { PER_PAGE } from "./recommendation";

export function Pagination({ page, pageTotal, total, onChange }: { page: number; pageTotal: number; total: number; onChange: (page: number) => void }) {
  const { t } = useI18n();
  const pageNumbers = Array.from({ length: pageTotal }, (_, index) => index + 1);
  return (
    <div className="recommendations-pagination">
      <span>{t("jobs.pagination.summary", { page, pageTotal, perPage: PER_PAGE, total })}</span>
      <div>
        <button className="secondary" disabled={page === 1} onClick={() => onChange(Math.max(1, page - 1))}>{t("jobs.pagination.previous")}</button>
        {pageNumbers.map((number) => number === page
          ? <span className="current-page" key={number}>{number}</span>
          : <button className="ghost page-number" key={number} onClick={() => onChange(number)}>{number}</button>)}
        <button className="secondary" disabled={page === pageTotal} onClick={() => onChange(Math.min(pageTotal, page + 1))}>{t("jobs.pagination.next")}</button>
      </div>
    </div>
  );
}
