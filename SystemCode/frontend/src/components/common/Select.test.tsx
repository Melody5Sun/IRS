import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Select } from "./Select";

// 让 React 知道这是测试环境，act 包裹的更新会同步完成
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// jsdom 没有实现 scrollIntoView
Element.prototype.scrollIntoView = () => {};

const OPTIONS = [{ value: "a", label: "Apple" }, { value: "b", label: "Banana" }, { value: "c", label: "Blueberry" }];
let container: HTMLDivElement;

function render(onChange: (value: string) => void, value = "a") {
  container = document.createElement("div");
  document.body.appendChild(container);
  act(() => createRoot(container).render(<Select value={value} options={OPTIONS} onChange={onChange} />));
  return container.querySelector("button")!;
}

const press = (target: Element, key: string) => act(() => { target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true })); });

afterEach(() => container.remove());

describe("Select", () => {
  it("opens with the arrow key, moves the highlight and picks with Enter", () => {
    const onChange = vi.fn();
    const trigger = render(onChange);
    press(trigger, "ArrowDown");
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    press(trigger, "ArrowDown");
    press(trigger, "Enter");
    expect(onChange).toHaveBeenCalledWith("b");
    expect(container.querySelector("[role=listbox]")).toBeNull();
  });

  it("jumps by first letter, cycling through options with the same letter", () => {
    const onChange = vi.fn();
    const trigger = render(onChange);
    press(trigger, "b");
    press(trigger, "b");
    press(trigger, "Enter");
    expect(onChange).toHaveBeenCalledWith("c");
  });

  it("picks with the mouse and does not fire for the current value", () => {
    const onChange = vi.fn();
    const trigger = render(onChange);
    act(() => trigger.click());
    const options = container.querySelectorAll("[role=option]");
    act(() => { options[0].dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });
    expect(onChange).not.toHaveBeenCalled();
    act(() => trigger.click());
    act(() => { container.querySelectorAll("[role=option]")[2].dispatchEvent(new MouseEvent("mousedown", { bubbles: true })); });
    expect(onChange).toHaveBeenCalledWith("c");
  });
});
