import { describe, expect, it } from "vitest";
import { en } from "./en";
import { format, translate } from "./LanguageProvider";
import { zh } from "./zh";

describe("i18n dictionaries", () => {
  it("translates every English key into Chinese", () => {
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort());
    for (const [key, value] of Object.entries(zh)) expect(value.trim(), key).not.toBe("");
  });

  it("keeps the same placeholders in both languages", () => {
    const placeholders = (text: string) => (text.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(en) as Array<keyof typeof en>) expect(placeholders(zh[key]), key).toEqual(placeholders(en[key]));
  });

  it("interpolates variables and leaves unknown placeholders visible", () => {
    expect(format("{count} roles · {missing}", { count: 3 })).toBe("3 roles · {missing}");
    expect(translate("en", "jobs.filter.all", { count: 30 })).toBe("All 30");
    expect(translate("zh", "jobs.filter.all", { count: 30 })).toBe("全部 30");
  });
});
