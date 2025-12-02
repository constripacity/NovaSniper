document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("add-product-form");
  const messageEl = document.getElementById("form-message");

  const setMessage = (text, status) => {
    if (!messageEl) return;
    messageEl.textContent = text;
    messageEl.classList.remove("success", "error");
    if (status) {
      messageEl.classList.add(status);
    }
  };

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      setMessage("Submitting...", "");

      const formData = new FormData(form);
      const payload = {
        platform: formData.get("platform"),
        product_id: formData.get("product_identifier"),
        target_price: parseFloat(formData.get("target_price")),
        currency: formData.get("currency"),
        notify_email: formData.get("notify_email"),
      };

      if (!payload.product_id || Number.isNaN(payload.target_price)) {
        setMessage("Please fill in all fields correctly.", "error");
        return;
      }

      try {
        const res = await fetch("/tracked-products", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.detail || "Failed to add product");
        }

        setMessage("Product added successfully!", "success");
        setTimeout(() => window.location.reload(), 700);
      } catch (err) {
        console.error(err);
        setMessage(err.message, "error");
      }
    });
  }

  document.body.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;

    const id = btn.getAttribute("data-id");
    const action = btn.getAttribute("data-action");

    if (action === "delete") {
      if (!confirm("Delete this tracked product?")) return;
      try {
        const res = await fetch(`/tracked-products/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error("Failed to delete product");
        window.location.reload();
      } catch (err) {
        alert(err.message);
      }
    }

    if (action === "check") {
      btn.disabled = true;
      btn.textContent = "Checking...";
      try {
        const res = await fetch(`/tracked-products/${id}/check-now`, {
          method: "POST",
        });
        if (!res.ok) throw new Error("Failed to trigger check");
        window.location.reload();
      } catch (err) {
        alert(err.message);
        btn.disabled = false;
        btn.textContent = "Check Now";
      }
    }
  });
});
