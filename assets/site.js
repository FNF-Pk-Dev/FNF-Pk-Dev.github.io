/* ==========================================================================
   Parker Engine 中文文档站 — 站点脚本
   MDUI 自带组件（抽屉、提示、面板）由 mdui.min.js 自动初始化，这里只补四件事：
   1) 防御性调用 mdui.mutation()（动态插入的 mdui 组件也能被初始化）
   2) 宽屏下按 MDUI 的内部约定补上抽屉的初始展开状态
   3) 给每个代码块加一个「复制」按钮
   4) 窄屏点击侧边栏链接后收起抽屉
   无任何外部依赖。
   ========================================================================== */
(function () {
	"use strict";

	function onReady(fn) {
		if (document.readyState === "loading") {
			document.addEventListener("DOMContentLoaded", fn);
		} else {
			fn();
		}
	}

	/* ---------------------------------------------------------------------
	   3. 代码块复制按钮
	   --------------------------------------------------------------------- */
	function addCopyButtons() {
		var blocks = document.querySelectorAll(".pk-doc pre");
		Array.prototype.forEach.call(blocks, function (pre) {
			if (pre.getAttribute("data-pk-copy") === "1") {
				return;
			}
			pre.setAttribute("data-pk-copy", "1");

			var btn = document.createElement("button");
			btn.type = "button";
			btn.className = "pk-copy-btn";
			btn.textContent = "复制";
			btn.setAttribute("aria-label", "复制这段代码");

			btn.addEventListener("click", function () {
				var code = pre.querySelector("code");
				var text = (code || pre).innerText.replace(/\s+$/, "");
				copyText(text, btn);
			});

			var wrapper = document.createElement("div");
			wrapper.className = "pk-code-wrap";
			pre.parentNode.insertBefore(wrapper, pre);
			wrapper.appendChild(pre);
			wrapper.appendChild(btn);
		});
	}

	function copyText(text, btn) {
		function done(ok) {
			var old = btn.textContent;
			btn.textContent = ok ? "已复制" : "复制失败";
			btn.classList.add(ok ? "pk-copy-ok" : "pk-copy-fail");
			window.setTimeout(function () {
				btn.textContent = old;
				btn.classList.remove("pk-copy-ok", "pk-copy-fail");
			}, 1500);
		}

		if (navigator.clipboard && navigator.clipboard.writeText) {
			navigator.clipboard.writeText(text).then(
				function () {
					done(true);
				},
				function () {
					done(fallbackCopy(text));
				}
			);
			return;
		}
		done(fallbackCopy(text));
	}

	function fallbackCopy(text) {
		var area = document.createElement("textarea");
		area.value = text;
		area.setAttribute("readonly", "readonly");
		area.style.position = "fixed";
		area.style.top = "-1000px";
		document.body.appendChild(area);
		area.select();
		var ok = false;
		try {
			ok = document.execCommand("copy");
		} catch (e) {
			ok = false;
		}
		document.body.removeChild(area);
		return ok;
	}

	/* ---------------------------------------------------------------------
	   2. 侧边栏（MDUI Drawer）
	   MDUI 的 [mdui-drawer] 属性写法有两个坑，所以这里自己接管：
	   a) 桌面宽度下它只把内部状态置为 opened，不补 mdui-drawer-open 与
	      body 的 mdui-drawer-body-left，侧边栏初始不可见；
	   b) 开关只监听 click，触摸设备上不一定收到 click。
	   做法：自己 new mdui.Drawer()，click 与 touchend 都接，并按 DOM 上的
	   mdui-drawer-open 类决定开还是关，保证视觉与内部状态一致。
	   --------------------------------------------------------------------- */
	function initDrawer() {
		var drawer = document.getElementById("pk-drawer");
		var toggle = document.querySelector(".pk-drawer-toggle");
		if (!drawer || !toggle || !window.mdui || !window.mdui.Drawer) {
			return null;
		}
		var instance = new window.mdui.Drawer(drawer, { overlay: false });
		var lastToggle = 0;

		function toggleDrawer() {
			var now = Date.now();
			if (now - lastToggle < 500) {
				return;
			}
			lastToggle = now;
			if (drawer.classList.contains("mdui-drawer-open")) {
				instance.close();
			} else {
				instance.open();
			}
		}

		toggle.addEventListener("click", toggleDrawer);
		toggle.addEventListener(
			"touchend",
			function (event) {
				// 阻止浏览器合成 click，避免同一次点击被处理两次
				event.preventDefault();
				toggleDrawer();
			},
			false
		);

		// 窄屏点击侧边栏内的链接后收起抽屉
		drawer.addEventListener("click", function (event) {
			var link = event.target.closest ? event.target.closest("a") : null;
			if (link && window.innerWidth < 1024) {
				instance.close();
			}
		});

		syncDrawer(drawer);
		window.addEventListener(
			"resize",
			debounce(function () {
				syncDrawer(drawer);
			}, 150)
		);
		return instance;
	}

	function syncDrawer(drawer) {
		if (!drawer || window.innerWidth < 1024) {
			return;
		}
		if (drawer.classList.contains("mdui-drawer-close")) {
			return;
		}
		drawer.classList.add("mdui-drawer-open");
		document.body.classList.add("mdui-drawer-body-left");
	}

	function debounce(fn, wait) {
		var timer = null;
		return function () {
			window.clearTimeout(timer);
			timer = window.setTimeout(fn, wait);
		};
	}

	onReady(function () {
		// MDUI 会在 DOM 就绪后自动初始化带 mdui-* 属性的组件；
		// 这里再扫一遍，覆盖脚本动态插入的内容。
		if (window.mdui && window.mdui.mutation) {
			window.mdui.mutation();
		}
		initDrawer();
		addCopyButtons();
	});
})();
