frappe.ready(function () {
	const ROOT = document.getElementById("partner-artigos");
	if (!ROOT) return;

	const STORAGE_KEY = "logicpos_partner_cart";
	const apiList = ROOT.dataset.apiList;
	const apiQuote = ROOT.dataset.apiQuote;

	const els = {
		grid: document.getElementById("artigos-grid"),
		empty: document.getElementById("artigos-empty"),
		pagination: document.getElementById("artigos-pagination"),
		search: document.getElementById("artigos-search"),
		cartCount: document.getElementById("artigos-cart-count"),
		cartToggle: document.getElementById("artigos-cart-toggle"),
		drawer: document.getElementById("artigos-drawer"),
		drawerClose: document.getElementById("artigos-drawer-close"),
		cartList: document.getElementById("artigos-cart-list"),
		cartTotal: document.getElementById("artigos-cart-total"),
		notes: document.getElementById("artigos-notes"),
		requestBtn: document.getElementById("artigos-request-quote"),
		priceListLabel: document.getElementById("artigos-price-list-label"),
	};

	let state = { page: 1, pageSize: 20, total: 0, search: "", loading: false };

	function loadCart() {
		try {
			return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
		} catch (e) {
			return [];
		}
	}

	function saveCart(cart) {
		localStorage.setItem(STORAGE_KEY, JSON.stringify(cart));
		renderCart();
	}

	function formatMoney(amount, currency) {
		if (typeof format_currency === "function") {
			return format_currency(amount, currency || "EUR");
		}
		return (currency || "EUR") + " " + Number(amount || 0).toFixed(2);
	}

	function escapeHtml(value) {
		if (frappe.utils && typeof frappe.utils.escape_html === "function") {
			return frappe.utils.escape_html(value || "");
		}
		return String(value || "")
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}

	function fetchArticles() {
		if (state.loading) return;
		state.loading = true;
		frappe.call({
			method: apiList,
			args: {
				search: state.search || null,
				page: state.page,
				page_size: state.pageSize,
			},
			callback: function (r) {
				state.loading = false;
				const data = (r && r.message) || {};
				state.total = data.total || 0;
				if (els.priceListLabel && data.price_list) {
					els.priceListLabel.textContent = __("Preços da lista {0}", [
						data.price_list,
					]);
				}
				renderGrid(data.items || []);
				renderPagination();
			},
			error: function () {
				state.loading = false;
				els.grid.innerHTML = "";
				els.empty.textContent = __("Não foi possível carregar os artigos.");
				els.empty.classList.remove("d-none");
			},
		});
	}

	function renderGrid(items) {
		els.grid.innerHTML = "";
		els.empty.textContent = __("Nenhum artigo encontrado.");
		els.empty.classList.toggle("d-none", items.length > 0);
		items.forEach(function (item) {
			const card = document.createElement("article");
			card.className = "partner-artigos-card";
			const img = item.image
				? `<img src="${escapeHtml(item.image)}" alt="">`
				: `<i class="fa-solid fa-box" style="color:#94a3b8;font-size:2rem" aria-hidden="true"></i>`;
			card.innerHTML = `
				<div class="partner-artigos-card-image">${img}</div>
				<div class="partner-artigos-card-body">
					<p class="partner-artigos-card-code">${escapeHtml(item.item_code)}</p>
					<h3 class="partner-artigos-card-name">${escapeHtml(item.item_name || "")}</h3>
					<p class="partner-artigos-card-price">${formatMoney(item.price_list_rate, item.currency)}</p>
					<button type="button" class="btn btn-sm btn-secondary btn-block">${__("Adicionar")}</button>
				</div>`;
			card.querySelector("button").addEventListener("click", function () {
				addToCart(item);
			});
			els.grid.appendChild(card);
		});
	}

	function renderPagination() {
		els.pagination.innerHTML = "";
		const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
		if (pages <= 1) return;

		const prev = document.createElement("button");
		prev.className = "btn btn-sm btn-light";
		prev.textContent = __("Anterior");
		prev.disabled = state.page <= 1;
		prev.onclick = function () {
			state.page -= 1;
			fetchArticles();
		};

		const next = document.createElement("button");
		next.className = "btn btn-sm btn-light";
		next.textContent = __("Seguinte");
		next.disabled = state.page >= pages;
		next.onclick = function () {
			state.page += 1;
			fetchArticles();
		};

		const info = document.createElement("span");
		info.textContent = state.page + " / " + pages;
		els.pagination.append(prev, info, next);
	}

	function addToCart(item) {
		const cart = loadCart();
		const existing = cart.find(function (c) {
			return c.item_code === item.item_code;
		});
		if (existing) {
			existing.qty += 1;
		} else {
			cart.push({
				item_code: item.item_code,
				item_name: item.item_name,
				qty: 1,
				price_list_rate: item.price_list_rate,
				currency: item.currency,
			});
		}
		saveCart(cart);
		frappe.show_alert({ message: __("Adicionado ao carrinho"), indicator: "green" });
	}

	function renderCart() {
		const cart = loadCart();
		const count = cart.reduce(function (s, c) {
			return s + (c.qty || 0);
		}, 0);
		els.cartCount.textContent = String(count);
		els.requestBtn.disabled = count === 0;
		els.cartList.innerHTML = "";
		let total = 0;
		let currency = "EUR";
		cart.forEach(function (line) {
			currency = line.currency || currency;
			total += (line.price_list_rate || 0) * (line.qty || 0);
			const li = document.createElement("li");
			li.innerHTML = `
				<div>
					<strong>${escapeHtml(line.item_name || line.item_code)}</strong>
					<div class="text-muted small">${escapeHtml(line.item_code)}</div>
					<div class="mt-1">
						<button type="button" class="btn btn-xs btn-light" data-act="dec">−</button>
						<span class="mx-1">${line.qty}</span>
						<button type="button" class="btn btn-xs btn-light" data-act="inc">+</button>
						<button type="button" class="btn btn-xs btn-link text-danger" data-act="rm">${__("Remover")}</button>
					</div>
				</div>
				<div>${formatMoney((line.price_list_rate || 0) * line.qty, currency)}</div>`;
			li.querySelector('[data-act="dec"]').onclick = function () {
				updateQty(line.item_code, -1);
			};
			li.querySelector('[data-act="inc"]').onclick = function () {
				updateQty(line.item_code, 1);
			};
			li.querySelector('[data-act="rm"]').onclick = function () {
				removeLine(line.item_code);
			};
			els.cartList.appendChild(li);
		});
		els.cartTotal.textContent = count ? formatMoney(total, currency) : "—";
	}

	function updateQty(item_code, delta) {
		const cart = loadCart();
		const line = cart.find(function (c) {
			return c.item_code === item_code;
		});
		if (!line) return;
		line.qty += delta;
		if (line.qty <= 0) {
			saveCart(
				cart.filter(function (c) {
					return c.item_code !== item_code;
				})
			);
		} else {
			saveCart(cart);
		}
	}

	function removeLine(item_code) {
		saveCart(
			loadCart().filter(function (c) {
				return c.item_code !== item_code;
			})
		);
	}

	function openDrawer(open) {
		if (open) {
			els.drawer.hidden = false;
			els.cartToggle.setAttribute("aria-expanded", "true");
		} else {
			els.drawer.hidden = true;
			els.cartToggle.setAttribute("aria-expanded", "false");
		}
	}

	els.cartToggle.addEventListener("click", function () {
		openDrawer(els.drawer.hidden);
	});
	els.drawerClose.addEventListener("click", function () {
		openDrawer(false);
	});
	els.drawer.addEventListener("click", function (e) {
		if (e.target === els.drawer) openDrawer(false);
	});

	let searchTimer = null;
	els.search.addEventListener("input", function () {
		clearTimeout(searchTimer);
		searchTimer = setTimeout(function () {
			state.search = els.search.value.trim();
			state.page = 1;
			fetchArticles();
		}, 300);
	});

	els.requestBtn.addEventListener("click", function () {
		const cart = loadCart();
		if (!cart.length) return;
		els.requestBtn.disabled = true;
		frappe.call({
			method: apiQuote,
			args: {
				items: cart.map(function (c) {
					return { item_code: c.item_code, qty: c.qty };
				}),
				notes: els.notes.value || null,
			},
			callback: function (r) {
				if (r.message && r.message.ok) {
					frappe.msgprint({
						title: __("Pedido enviado"),
						message: __("O pedido de orçamento foi enviado à equipa comercial."),
						indicator: "green",
					});
					saveCart([]);
					els.notes.value = "";
					openDrawer(false);
				}
				els.requestBtn.disabled = loadCart().length === 0;
			},
			error: function () {
				els.requestBtn.disabled = loadCart().length === 0;
			},
		});
	});

	renderCart();
	fetchArticles();
});
