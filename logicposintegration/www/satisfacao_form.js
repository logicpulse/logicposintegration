(function () {
	function ready(fn) {
		if (document.readyState !== "loading") {
			fn();
		} else {
			document.addEventListener("DOMContentLoaded", fn);
		}
	}

	ready(function () {
		var form = document.getElementById("sat-form");
		if (!form || typeof frappe === "undefined") {
			return;
		}

		var token = form.getAttribute("data-token");
		var api = form.getAttribute("data-api");
		var submitBtn = document.getElementById("sat-submit");
		var hint = document.getElementById("sat-hint");
		var thanks = document.getElementById("sat-thanks");

		form.querySelectorAll(".sat-pill, .sat-scale-btn").forEach(function (btn) {
			btn.addEventListener("click", function () {
				var group = btn.parentElement;
				group.querySelectorAll("button").forEach(function (b) {
					b.classList.remove("is-selected");
				});
				btn.classList.add("is-selected");
			});
		});

		function collectAnswers() {
			var answers = [];
			form.querySelectorAll(".sat-question").forEach(function (section) {
				var idx = parseInt(section.getAttribute("data-idx"), 10);
				var type = section.getAttribute("data-type");
				var row = {
					idx: idx,
					answer_scale: null,
					answer_text: null,
					answer_choice: null,
				};
				if (type === "Choice") {
					var selected = section.querySelector(".sat-pill.is-selected");
					row.answer_choice = selected ? selected.getAttribute("data-value") : "";
				} else if (type === "Scale") {
					var scaleBtn = section.querySelector(".sat-scale-btn.is-selected");
					row.answer_scale = scaleBtn
						? parseInt(scaleBtn.getAttribute("data-value"), 10)
						: null;
				} else {
					var ta = section.querySelector("textarea");
					row.answer_text = ta ? ta.value : "";
				}
				answers.push(row);
			});
			return answers;
		}

		function showHint(msg, isError) {
			if (!hint) {
				return;
			}
			hint.hidden = false;
			hint.textContent = msg;
			hint.classList.toggle("is-error", !!isError);
		}

		submitBtn.addEventListener("click", function () {
			submitBtn.disabled = true;
			frappe.call({
				method: api,
				args: {
					token: token,
					answers: JSON.stringify(collectAnswers()),
				},
				callback: function () {
					form.hidden = true;
					if (thanks) {
						thanks.hidden = false;
					}
				},
				error: function (r) {
					submitBtn.disabled = false;
					var msg =
						(r && r.message) ||
						(typeof __ !== "undefined"
							? __("Não foi possível submeter o inquérito.")
							: "Não foi possível submeter o inquérito.");
					showHint(msg, true);
				},
			});
		});
	});
})();
