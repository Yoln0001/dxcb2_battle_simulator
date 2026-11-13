"use strict";
(() => {
  let timer;
  window.showToast = (text) => {
    const box = document.querySelector("#toast");
    box.textContent = text;
    clearTimeout(timer);
    if (typeof box.showPopover === "function") {
      if (!box.matches(":popover-open")) box.showPopover();
    } else {
      const dialogs = [...document.querySelectorAll("dialog[open]")];
      (dialogs.at(-1) || document.body).append(box);
    }
    box.classList.add("visible");
    timer = setTimeout(() => {
      box.classList.remove("visible");
      if (typeof box.hidePopover === "function" && box.matches(":popover-open")) box.hidePopover();
    }, 3000);
  };
})();
