const appState = {
  quotation: {
    dbId: null,
    number: "",
    date: "",
    client: "",
    attention: "",
    city: "",
    validity: "15 días",
    paymentTerms: "",
    notes: ""
  },
  items: [],
  selectedItemId: null
};

function generateId() {
  return "item_" + Date.now() + "_" + Math.floor(Math.random() * 1000000);
}

function createEmptyItem() {
  return {
    id: generateId(),
    dbItemId: null,
    templateId: null,
    title: "Nuevo equipo",
    brand: "",
    model: "",
    origin: "",
    warranty: "",
    price: "",
    quantity: "1",
    showPrice: false,
    subtitle: "",
    descriptionLong: "",
    highlights: [],
    specs: [],
    uses: [],
    accessories: [],
    advantages: [],
    imageSrc: ""
  };
}
function normalizeTemplateSpecs(specs) {
  if (!Array.isArray(specs)) return [];
  return specs
    .map(row => ({
      param: row?.param ?? row?.parametro ?? "",
      value: row?.value ?? row?.detalle ?? ""
    }))
    .filter(row => row.param || row.value);
}

function normalizeTemplateTextList(rows) {
  if (!Array.isArray(rows)) return [];
  return rows
    .map(row => {
      if (typeof row === "string") return row;
      return row?.texto ?? "";
    })
    .map(text => String(text || "").trim())
    .filter(Boolean);
}
function resolveTemplateImageSrc(template) {
  const rawUrl = String(template?.imagen_url || "").trim();
  if (rawUrl) return rawUrl;

  const rawImage = String(template?.imagen || "").trim();
  if (!rawImage) return "";

  if (rawImage.startsWith("/static/")) return rawImage;
  if (rawImage.startsWith("static/")) return `/${rawImage}`;
  if (rawImage.startsWith("http://") || rawImage.startsWith("https://")) return rawImage;

  return `/static/${rawImage}`;
}
function createItemFromTemplate(template) {
  return {
    id: generateId(),
    dbItemId: null,
    templateId: template.id,
    title: template.nombre_comercial || template.nombre_plantilla || template.equipo_nombre || "Nuevo equipo",
    brand: template.equipo_marca || "",
    model: template.equipo_modelo || "",
    origin: "",
    warranty: "",
    price: template.precio_base ? String(template.precio_base) : "",
    quantity: "1",
    showPrice: !!template.mostrar_precio_por_defecto,
    subtitle: template.descripcion_breve || "",
    descriptionLong: template.descripcion_larga || "",
    highlights: [],
    specs: normalizeTemplateSpecs(template.especificaciones),
    uses: normalizeTemplateTextList(template.usos),
    accessories: normalizeTemplateTextList(template.accesorios),
    advantages: normalizeTemplateTextList(template.ventajas),
    imageSrc: resolveTemplateImageSrc(template)
  };
}

function getSelectedItem() {
  return appState.items.find(item => item.id === appState.selectedItemId) || null;
}

function setSelectedItem(id) {
  appState.selectedItemId = id;
  renderAll();
}

function addItem() {
  const item = createEmptyItem();
  appState.items.push(item);
  appState.selectedItemId = item.id;
  renderAll();
}

function addItemFromTemplate(templateId) {
  const templates = window.PLANTILLAS_DATA || [];
  const found = templates.find(t => String(t.id) === String(templateId));
  if (!found) return;

  const item = createItemFromTemplate(found);
  appState.items.push(item);
  appState.selectedItemId = item.id;
  renderAll();
}

function duplicateSelectedItem() {
  const item = getSelectedItem();
  if (!item) return;

  const clone = structuredClone(item);
  clone.id = generateId();
  clone.dbItemId = null;
  clone.title = `${item.title} (copia)`;
  appState.items.push(clone);
  appState.selectedItemId = clone.id;
  renderAll();
}

function deleteSelectedItem() {
  const id = appState.selectedItemId;
  if (!id) return;

  appState.items = appState.items.filter(item => item.id !== id);
  appState.selectedItemId = appState.items.length ? appState.items[0].id : null;
  renderAll();
}

function resetQuotation() {
  appState.quotation = {
    dbId: null,
    number: "",
    date: "",
    client: "",
    attention: "",
    city: "",
    validity: "15 días",
    paymentTerms: "",
    notes: ""
  };
  appState.items = [];
  appState.selectedItemId = null;
  addItem();
}

function formatPrice(value) {
  if (value === null || value === undefined || value === "") return "";
  return `Bs. ${value}`;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function nl2br(text) {
  return escapeHtml(text || "").replace(/\n/g, "<br>");
}

function bindQuotationFields() {
  const mappings = {
    qNumber: "number",
    qDate: "date",
    qClient: "client",
    qAttention: "attention",
    qCity: "city",
    qValidity: "validity",
    qPaymentTerms: "paymentTerms",
    qNotes: "notes"
  };

  Object.entries(mappings).forEach(([id, key]) => {
    const el = document.getElementById(id);
    if (!el) return;

    el.addEventListener("input", () => {
      appState.quotation[key] = el.value;
      renderPreview();
    });
  });
}

function populateQuotationFields() {
  const q = appState.quotation;
  document.getElementById("qNumber").value = q.number || "";
  document.getElementById("qDate").value = q.date || "";
  document.getElementById("qClient").value = q.client || "";
  document.getElementById("qAttention").value = q.attention || "";
  document.getElementById("qCity").value = q.city || "";
  document.getElementById("qValidity").value = q.validity || "";
  document.getElementById("qPaymentTerms").value = q.paymentTerms || "";
  document.getElementById("qNotes").value = q.notes || "";
}

function bindItemMainFields() {
  const map = [
    ["itemTitle", "title"],
    ["itemBrand", "brand"],
    ["itemModel", "model"],
    ["itemOrigin", "origin"],
    ["itemWarranty", "warranty"],
    ["itemPrice", "price"],
    ["itemQuantity", "quantity"],
    ["itemSubtitle", "subtitle"],
    ["itemDescriptionLong", "descriptionLong"],
    ["itemImageUrl", "imageSrc"]
  ];

  map.forEach(([id, key]) => {
    const el = document.getElementById(id);
    if (!el) return;

    el.addEventListener("input", (e) => {
      const item = getSelectedItem();
      if (!item) return;
      item[key] = e.target.value;
      renderAll();
    });
  });

  const showPrice = document.getElementById("itemShowPrice");
  if (showPrice) {
    showPrice.addEventListener("change", (e) => {
      const item = getSelectedItem();
      if (!item) return;
      item.showPrice = e.target.checked;
      renderPreview();
    });
  }

  const imageUpload = document.getElementById("itemImageUpload");
  if (imageUpload) {
    imageUpload.addEventListener("change", async (e) => {
      const item = getSelectedItem();
      if (!item) return;

      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("image", file);

      try {
        const res = await fetch("/upload-image", {
          method: "POST",
          body: formData
        });

        const data = await res.json();

        if (!res.ok || !data.ok) {
          alert(data.error || "No se pudo subir la imagen.");
          return;
        }

        item.imageSrc = data.url || "";
        document.getElementById("itemImageUrl").value = item.imageSrc;
        renderAll();
      } catch (err) {
        console.error(err);
        alert("Error subiendo imagen.");
      } finally {
        e.target.value = "";
      }
    });
  }
}

function populateItemFields() {
  const item = getSelectedItem();
  const empty = !item;

  const setValue = (id, value = "") => {
    const el = document.getElementById(id);
    if (el) el.value = value;
  };

  setValue("itemTitle", empty ? "" : item.title);
  setValue("itemBrand", empty ? "" : item.brand);
  setValue("itemModel", empty ? "" : item.model);
  setValue("itemOrigin", empty ? "" : item.origin);
  setValue("itemWarranty", empty ? "" : item.warranty);
  setValue("itemPrice", empty ? "" : item.price);
  setValue("itemQuantity", empty ? "1" : (item.quantity || "1"));
  setValue("itemSubtitle", empty ? "" : item.subtitle);
  setValue("itemDescriptionLong", empty ? "" : item.descriptionLong);
  setValue("itemImageUrl", empty ? "" : (item.imageSrc && !item.imageSrc.startsWith("data:") ? item.imageSrc : ""));

  const showPrice = document.getElementById("itemShowPrice");
  if (showPrice) showPrice.checked = empty ? false : item.showPrice;
}

function renderItemsList() {
  const container = document.getElementById("itemsList");
  if (!container) return;

  container.innerHTML = "";

  appState.items.forEach((item, index) => {
    const qty = item.quantity || "1";
    const div = document.createElement("div");
    div.className = `item-card ${item.id === appState.selectedItemId ? "active" : ""}`;
    div.innerHTML = `
      <strong>${escapeHtml(item.title || `Equipo ${index + 1}`)}</strong>
      <span>${escapeHtml(item.brand || "")} ${escapeHtml(item.model || "")} | Cant: ${escapeHtml(qty)}</span>
    `;
    div.addEventListener("click", () => setSelectedItem(item.id));
    container.appendChild(div);
  });
}

function renderSimpleListEditor(containerId, items, type) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = "";

  items.forEach((value, index) => {
    const row = document.createElement("div");
    row.className = "editor-row";
    row.innerHTML = `
      <input type="text" value="${String(value).replace(/"/g, "&quot;")}" />
      <div class="row-actions">
        <button class="btn btn-danger btn-small" type="button">Eliminar</button>
      </div>
    `;

    row.querySelector("input").addEventListener("input", (e) => {
      const item = getSelectedItem();
      if (!item) return;
      item[type][index] = e.target.value;
      renderPreview();
    });

    row.querySelector("button").addEventListener("click", () => {
      const item = getSelectedItem();
      if (!item) return;
      item[type].splice(index, 1);
      renderEditors();
      renderPreview();
    });

    container.appendChild(row);
  });
}

function renderSpecsEditor() {
  const item = getSelectedItem();
  const container = document.getElementById("specsEditor");
  if (!container) return;

  container.innerHTML = "";
  if (!item) return;

  item.specs.forEach((row, index) => {
    const div = document.createElement("div");
    div.className = "editor-row";
    div.innerHTML = `
      <input type="text" placeholder="Parámetro" value="${String(row.param || "").replace(/"/g, "&quot;")}" />
      <textarea placeholder="Detalle">${row.value || ""}</textarea>
      <div class="row-actions">
        <button class="btn btn-danger btn-small" type="button">Eliminar</button>
      </div>
    `;

    const paramInput = div.querySelector("input");
    const valueTextarea = div.querySelector("textarea");
    const removeBtn = div.querySelector("button");

    paramInput.addEventListener("input", (e) => {
      item.specs[index].param = e.target.value;
      renderPreview();
    });

    valueTextarea.addEventListener("input", (e) => {
      item.specs[index].value = e.target.value;
      renderPreview();
    });

    removeBtn.addEventListener("click", () => {
      item.specs.splice(index, 1);
      renderEditors();
      renderPreview();
    });

    container.appendChild(div);
  });
}

function renderEditors() {
  const item = getSelectedItem();
  renderSimpleListEditor("highlightsEditor", item ? item.highlights : [], "highlights");
  renderSpecsEditor();
  renderSimpleListEditor("usesEditor", item ? item.uses : [], "uses");
  renderSimpleListEditor("accessoriesEditor", item ? item.accessories : [], "accessories");
  renderSimpleListEditor("advantagesEditor", item ? item.advantages : [], "advantages");
}
function chunkArray(arr, size) {
  if (!Array.isArray(arr) || !arr.length) return [];
  const chunks = [];
  for (let i = 0; i < arr.length; i += size) {
    chunks.push(arr.slice(i, i + size));
  }
  return chunks;
}

function splitLongText(text, maxChars = 680) {
  const clean = String(text || "").trim();
  if (!clean) return [];

  const paragraphs = clean
    .split(/\n{2,}/)
    .map(p => p.trim())
    .filter(Boolean);

  const parts = [];

  paragraphs.forEach(paragraph => {
    if (paragraph.length <= maxChars) {
      parts.push(paragraph);
      return;
    }

    let start = 0;
    while (start < paragraph.length) {
      let end = Math.min(start + maxChars, paragraph.length);

      if (end < paragraph.length) {
        const lastBreak = Math.max(
          paragraph.lastIndexOf(". ", end),
          paragraph.lastIndexOf("; ", end),
          paragraph.lastIndexOf(": ", end),
          paragraph.lastIndexOf(", ", end),
          paragraph.lastIndexOf(" ", end)
        );

        if (lastBreak > start + 180) {
          end = lastBreak + 1;
        }
      }

      const slice = paragraph.slice(start, end).trim();
      if (slice) parts.push(slice);
      start = end;
    }
  });

  return parts.filter(Boolean);
}

function estimateTextUnits(text, charsPerUnit = 90) {
  const clean = String(text || "").trim();
  if (!clean) return 0;

  const charUnits = Math.ceil(clean.length / charsPerUnit);
  const lineBreakUnits = (clean.match(/\n/g) || []).length;
  const paragraphUnits = (clean.match(/\n{2,}/g) || []).length * 2;

  return Math.max(1, charUnits + lineBreakUnits + paragraphUnits);
}

function estimateSpecUnits(spec) {
  const param = String(spec?.param || spec?.parametro || "").trim();
  const value = String(spec?.value || spec?.detalle || "").trim();

  const paramUnits = Math.ceil(param.length / 38);
  const valueUnits = Math.ceil(value.length / 58);
  const lineBreakUnits = (value.match(/\n/g) || []).length;

  return Math.max(1, paramUnits + valueUnits + lineBreakUnits);
}

function estimateListItemUnits(text, charsPerUnit = 42) {
  return estimateTextUnits(text, charsPerUnit);
}

function takeTextPartsByBudget(parts, startIndex, maxUnits) {
  let used = 0;
  let i = startIndex;
  const taken = [];

  while (i < parts.length) {
    const units = estimateTextUnits(parts[i], 90);

    if (taken.length > 0 && used + units > maxUnits) break;

    if (taken.length === 0 && units > maxUnits) {
      taken.push(parts[i]);
      i += 1;
      break;
    }

    taken.push(parts[i]);
    used += units;
    i += 1;
  }

  return {
    items: taken,
    nextIndex: i,
    usedUnits: used
  };
}

function takeSimpleListByBudget(items, startIndex, maxUnits, charsPerUnit = 42) {
  let used = 0;
  let i = startIndex;
  const taken = [];

  while (i < items.length) {
    const units = estimateListItemUnits(items[i], charsPerUnit);

    if (taken.length > 0 && used + units > maxUnits) break;

    if (taken.length === 0 && units > maxUnits) {
      taken.push(items[i]);
      i += 1;
      break;
    }

    taken.push(items[i]);
    used += units;
    i += 1;
  }

  return {
    items: taken,
    nextIndex: i,
    usedUnits: used
  };
}

function takeSpecsByBudget(items, startIndex, maxUnits) {
  let used = 0;
  let i = startIndex;
  const taken = [];

  while (i < items.length) {
    const units = estimateSpecUnits(items[i]);

    if (taken.length > 0 && used + units > maxUnits) break;

    if (taken.length === 0 && units > maxUnits) {
      taken.push(items[i]);
      i += 1;
      break;
    }

    taken.push(items[i]);
    used += units;
    i += 1;
  }

  return {
    items: taken,
    nextIndex: i,
    usedUnits: used
  };
}

function getPageBudgets(item, pageNo) {
  const hasImage = !!(item && item.imageSrc);

  if (pageNo === 0) {
    return {
      left: 19,
      right: hasImage ? 9 : 13
    };
  }

  return {
    left: 24,
    right: 18
  };
}

function buildHeaderMetaGrid(item, qty, subtotal, showSubtotal = true) {
  return `
    <div class="meta-grid">
      <div class="meta"><span class="k">Marca</span><span class="v">${escapeHtml(item.brand || "")}</span></div>
      <div class="meta"><span class="k">Modelo</span><span class="v">${escapeHtml(item.model || "")}</span></div>
      <div class="meta"><span class="k">Origen</span><span class="v">${escapeHtml(item.origin || "")}</span></div>
      <div class="meta"><span class="k">Garantía</span><span class="v">${escapeHtml(item.warranty || "")}</span></div>
    </div>

    <div class="meta-grid" style="margin-top:12px;">
      <div class="meta"><span class="k">Cantidad</span><span class="v">${escapeHtml(qty)}</span></div>
      ${item.showPrice ? `<div class="meta"><span class="k">Precio unitario</span><span class="v">${escapeHtml(formatPrice(item.price))}</span></div>` : `<div class="meta"><span class="k">Precio unitario</span><span class="v">No visible</span></div>`}
      ${showSubtotal ? `<div class="meta"><span class="k">Subtotal</span><span class="v">Bs. ${subtotal}</span></div>` : `<div class="meta"><span class="k">Documento</span><span class="v">Continuación</span></div>`}
    </div>
  `;
}

function buildDescriptionCard(descriptionPart, highlightsChunk) {
  if (!descriptionPart && !highlightsChunk.length) return "";

  return `
    <div class="card">
      ${descriptionPart ? `
        <h3 class="section-title">Descripción del equipo</h3>
        <p class="preview-text">${nl2br(descriptionPart)}</p>
      ` : ""}

      ${highlightsChunk.length ? `
        <h3 class="section-title">Características destacadas</h3>
        <ul class="clean">
          ${highlightsChunk.map(h => `<li>${escapeHtml(h)}</li>`).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function buildSpecsCard(specsChunk, title = "Especificaciones técnicas") {
  if (!specsChunk.length) return "";

  return `
    <div class="card">
      <h3 class="section-title">${title}</h3>
      <table class="spec-table">
        <thead>
          <tr>
            <th style="width:38%">Parámetro</th>
            <th>Detalle</th>
          </tr>
        </thead>
        <tbody>
          ${specsChunk.map(s => `
            <tr>
              <td>${escapeHtml(s.param || s.parametro || "")}</td>
              <td>${nl2br(s.value || s.detalle || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;
}

function buildImageAndListsCard(item, usesChunk, accessoriesChunk, advantagesChunk, showImage = true, titlePrefix = "") {
  if (!showImage && !usesChunk.length && !accessoriesChunk.length && !advantagesChunk.length) return "";

  return `
    <div class="card">
      ${showImage ? `
        <h3 class="section-title">${titlePrefix ? `${titlePrefix} · ` : ""}Imagen del equipo</h3>
        <div class="image-box">
          ${item.imageSrc
            ? `<img src="${item.imageSrc}" alt="${escapeHtml(item.title || "")}">`
            : `Sin imagen`
          }
        </div>
      ` : ""}

      ${usesChunk.length ? `
        <h3 class="section-title" style="margin-top:${showImage ? "16px" : "0"};">Aplicaciones / usos</h3>
        <div class="badge-row">
          ${usesChunk.map(u => `<span class="badge">${escapeHtml(u)}</span>`).join("")}
        </div>
      ` : ""}

      ${accessoriesChunk.length ? `
        <h3 class="section-title" style="margin-top:16px;">Contenido / accesorios</h3>
        <ul class="clean">
          ${accessoriesChunk.map(a => `<li>${escapeHtml(a)}</li>`).join("")}
        </ul>
      ` : ""}

      ${advantagesChunk.length ? `
        <h3 class="section-title" style="margin-top:16px;">Ventajas principales</h3>
        <ul class="clean">
          ${advantagesChunk.map(v => `<li>${escapeHtml(v)}</li>`).join("")}
        </ul>
      ` : ""}
    </div>
  `;
}

function buildItemPageFrame(item, options = {}) {
  const qty = item.quantity || "1";
  const subtotal = ((parseFloat(item.price || 0) || 0) * (parseFloat(qty || 1) || 1)).toFixed(2);

  const continuation = !!options.continuation;
  const continuationIndex = options.continuationIndex || 1;
  const topLeftHtml = options.topLeftHtml || "";
  const topRightHtml = options.topRightHtml || "";
  const bottomLeftHtml = options.bottomLeftHtml || "";
  const bottomRightHtml = options.bottomRightHtml || "";

  return `
    <section class="preview-page ${continuation ? "is-continuation" : ""}">
      <div class="left-band"></div>
      <div class="preview-content">
        <section class="preview-hero">
          <div>
            <img src="/static/logo_biosolutions.png" alt="BioSolutions" class="preview-logo" />
            ${continuation ? `<div class="continuation-chip">Continuación técnica · Página ${continuationIndex}</div>` : ""}
          </div>
          <div class="doc-chip">
            <span class="label">Documento</span>
            <span class="value ${continuation ? "is-continuation" : ""}">
              ${continuation ? "Ficha técnica complementaria" : "Ficha técnica"}
            </span>
          </div>
        </section>

        <section class="title-card">
          <span class="eyebrow">Equipo médico / laboratorio</span>
          <h1 class="doc-title">${escapeHtml(item.title || "")}</h1>
          <p class="subtitle">${escapeHtml(item.subtitle || "")}</p>
          ${buildHeaderMetaGrid(item, qty, subtotal, !continuation)}
        </section>

        <section class="main-grid">
          <div>${topLeftHtml}${bottomLeftHtml}</div>
          <div>${topRightHtml}${bottomRightHtml}</div>
        </section>
      </div>
    </section>
  `;
}

function buildItemPages(item) {
  const descriptionParts = splitLongText(item.descriptionLong || "", 680);
  const highlights = Array.isArray(item.highlights) ? item.highlights : [];
  const specs = Array.isArray(item.specs) ? item.specs : [];
  const uses = Array.isArray(item.uses) ? item.uses : [];
  const accessories = Array.isArray(item.accessories) ? item.accessories : [];
  const advantages = Array.isArray(item.advantages) ? item.advantages : [];

  let descIndex = 0;
  let highlightsIndex = 0;
  let specsIndex = 0;
  let usesIndex = 0;
  let accessoriesIndex = 0;
  let advantagesIndex = 0;

  const pages = [];
  let pageNo = 0;

  while (
    pageNo === 0 ||
    descIndex < descriptionParts.length ||
    highlightsIndex < highlights.length ||
    specsIndex < specs.length ||
    usesIndex < uses.length ||
    accessoriesIndex < accessories.length ||
    advantagesIndex < advantages.length
  ) {
    const isContinuation = pageNo > 0;
    const budgets = getPageBudgets(item, pageNo);

    let leftRemaining = budgets.left;
    let rightRemaining = budgets.right;

    let descriptionPart = "";
    let highlightsChunk = [];
    let specsChunkTop = [];
    let specsChunkBottom = [];
    let usesChunk = [];
    let accessoriesChunk = [];
    let advantagesChunk = [];

    if (!isContinuation) {
      const descTake = takeTextPartsByBudget(
        descriptionParts,
        descIndex,
        Math.max(6, leftRemaining - 5)
      );
      descriptionPart = descTake.items.join("\n\n");
      descIndex = descTake.nextIndex;
      leftRemaining -= descTake.usedUnits;

      const highlightsTake = takeSimpleListByBudget(
        highlights,
        highlightsIndex,
        Math.max(0, Math.min(4, leftRemaining)),
        48
      );
      highlightsChunk = highlightsTake.items;
      highlightsIndex = highlightsTake.nextIndex;
      leftRemaining -= highlightsTake.usedUnits;

      const specsTake = takeSpecsByBudget(
        specs,
        specsIndex,
        Math.max(0, leftRemaining)
      );
      specsChunkTop = specsTake.items;
      specsIndex = specsTake.nextIndex;
      leftRemaining -= specsTake.usedUnits;

      // En la primera página solo imagen + pocos usos.
            // En la primera página mantener imagen, pero aprovechar mejor el espacio libre.
      if (item.imageSrc) {
        rightRemaining -= 4;
      }

      const usesTake = takeSimpleListByBudget(
        uses,
        usesIndex,
        Math.max(0, Math.min(4, rightRemaining)),
        42
      );
      usesChunk = usesTake.items;
      usesIndex = usesTake.nextIndex;
      rightRemaining -= usesTake.usedUnits;

      const accessoriesTake = takeSimpleListByBudget(
        accessories,
        accessoriesIndex,
        Math.max(0, Math.min(3, rightRemaining)),
        42
      );
      accessoriesChunk = accessoriesTake.items;
      accessoriesIndex = accessoriesTake.nextIndex;
      rightRemaining -= accessoriesTake.usedUnits;

      const advantagesTake = takeSimpleListByBudget(
        advantages,
        advantagesIndex,
        Math.max(0, Math.min(2, rightRemaining)),
        42
      );
      advantagesChunk = advantagesTake.items;
      advantagesIndex = advantagesTake.nextIndex;
      rightRemaining -= advantagesTake.usedUnits;

    } else {
      // Continuación: prioridad técnica.
      const specsTakeTop = takeSpecsByBudget(
        specs,
        specsIndex,
        Math.max(0, Math.min(12, leftRemaining))
      );
      specsChunkTop = specsTakeTop.items;
      specsIndex = specsTakeTop.nextIndex;
      leftRemaining -= specsTakeTop.usedUnits;

      const specsTakeBottom = takeSpecsByBudget(
        specs,
        specsIndex,
        Math.max(0, leftRemaining)
      );
      specsChunkBottom = specsTakeBottom.items;
      specsIndex = specsTakeBottom.nextIndex;
      leftRemaining -= specsTakeBottom.usedUnits;

      const usesTake = takeSimpleListByBudget(
        uses,
        usesIndex,
        Math.max(0, Math.min(4, rightRemaining)),
        42
      );
      usesChunk = usesTake.items;
      usesIndex = usesTake.nextIndex;
      rightRemaining -= usesTake.usedUnits;

      const accessoriesTake = takeSimpleListByBudget(
        accessories,
        accessoriesIndex,
        Math.max(0, Math.min(7, rightRemaining)),
        42
      );
      accessoriesChunk = accessoriesTake.items;
      accessoriesIndex = accessoriesTake.nextIndex;
      rightRemaining -= accessoriesTake.usedUnits;

      const advantagesTake = takeSimpleListByBudget(
        advantages,
        advantagesIndex,
        Math.max(0, rightRemaining),
        42
      );
      advantagesChunk = advantagesTake.items;
      advantagesIndex = advantagesTake.nextIndex;
      rightRemaining -= advantagesTake.usedUnits;

      // Si ya no hay specs pero todavía sobra izquierda, meter texto restante.
      if (leftRemaining > 4 && descIndex < descriptionParts.length) {
        const descTakeExtra = takeTextPartsByBudget(
          descriptionParts,
          descIndex,
          leftRemaining
        );
        if (descTakeExtra.items.length) {
          descriptionPart = descTakeExtra.items.join("\n\n");
          descIndex = descTakeExtra.nextIndex;
          leftRemaining -= descTakeExtra.usedUnits;
        }
      }

      if (leftRemaining > 2 && highlightsIndex < highlights.length) {
        const highlightsTakeExtra = takeSimpleListByBudget(
          highlights,
          highlightsIndex,
          leftRemaining,
          48
        );
        highlightsChunk = highlightsTakeExtra.items;
        highlightsIndex = highlightsTakeExtra.nextIndex;
        leftRemaining -= highlightsTakeExtra.usedUnits;
      }
    }

    const hasRealLeftContent =
      !!descriptionPart ||
      highlightsChunk.length > 0 ||
      specsChunkTop.length > 0 ||
      specsChunkBottom.length > 0;

    const hasRealRightContent =
      (!isContinuation && !!item.imageSrc) ||
      usesChunk.length > 0 ||
      accessoriesChunk.length > 0 ||
      advantagesChunk.length > 0;

    if (pageNo > 0 && !hasRealLeftContent && !hasRealRightContent) {
      break;
    }

    const leftTop = buildDescriptionCard(descriptionPart, highlightsChunk);
    const leftBottom = buildSpecsCard(
      specsChunkTop,
      isContinuation ? "Especificaciones técnicas complementarias" : "Especificaciones técnicas"
    );

    const rightTop = buildImageAndListsCard(
      item,
      usesChunk,
      accessoriesChunk,
      advantagesChunk,
      !isContinuation,
      isContinuation ? "Continuación" : ""
    );

    const rightBottom = "";
    const extraLeftBottom = buildSpecsCard(specsChunkBottom, "Especificaciones técnicas complementarias");

    pages.push(
      buildItemPageFrame(item, {
        continuation: isContinuation,
        continuationIndex: pageNo + 1,
        topLeftHtml: leftTop,
        topRightHtml: rightTop,
        bottomLeftHtml: leftBottom + extraLeftBottom,
        bottomRightHtml: rightBottom
      })
    );

    pageNo += 1;
    if (pageNo > 60) break;
  }

  return pages;
}

function buildItemPage(item) {
  return buildItemPages(item).join("");
}

function buildTotalPage() {
  const total = appState.items.reduce((sum, item) => {
    const p = parseFloat(String(item.price || "").replace(/,/g, "").trim() || 0) || 0;
    const q = parseFloat(String(item.quantity || "").replace(/,/g, "").trim() || 1) || 1;
    return sum + (p * q);
  }, 0);

  return `
    <section class="preview-page">
      <div class="left-band"></div>
      <div class="preview-content">
        <section class="preview-hero">
          <div>
            <img src="/static/logo_biosolutions.png" alt="BioSolutions" class="preview-logo" />
          </div>
          <div class="doc-chip">
            <span class="label">Documento</span>
            <span class="value">Resumen final</span>
          </div>
        </section>

        <section class="title-card">
          <span class="eyebrow">Cotización consolidada</span>
          <h1 class="doc-title">${escapeHtml(appState.quotation.client || "Cliente")}</h1>
          <p class="subtitle">
            Número: ${escapeHtml(appState.quotation.number || "")}
            ${appState.quotation.date ? ` | Fecha: ${escapeHtml(appState.quotation.date)}` : ""}
          </p>

          <div class="meta-grid">
            <div class="meta"><span class="k">Atención</span><span class="v">${escapeHtml(appState.quotation.attention || "")}</span></div>
            <div class="meta"><span class="k">Ciudad</span><span class="v">${escapeHtml(appState.quotation.city || "")}</span></div>
            <div class="meta"><span class="k">Validez</span><span class="v">${escapeHtml(appState.quotation.validity || "")}</span></div>
            <div class="meta"><span class="k">Equipos</span><span class="v">${appState.items.length}</span></div>
          </div>
        </section>

        <div class="quote-summary">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Equipo</th>
                <th>Marca</th>
                <th>Modelo</th>
                <th>Cant.</th>
                <th>Precio</th>
                <th>Subtotal</th>
              </tr>
            </thead>
            <tbody>
              ${appState.items.map((item, index) => {
                const p = parseFloat(String(item.price || "").replace(/,/g, "").trim() || 0) || 0;
                const q = parseFloat(String(item.quantity || "").replace(/,/g, "").trim() || 1) || 1;
                const sub = (p * q).toFixed(2);
                return `
                  <tr>
                    <td>${index + 1}</td>
                    <td>${escapeHtml(item.title || "")}</td>
                    <td>${escapeHtml(item.brand || "")}</td>
                    <td>${escapeHtml(item.model || "")}</td>
                    <td>${escapeHtml(item.quantity || "1")}</td>
                    <td>${escapeHtml(formatPrice(item.price || ""))}</td>
                    <td>Bs. ${sub}</td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
        </div>

        <div class="total-box">
          <span class="label">Total referencial</span>
          <span class="value">Bs. ${total.toFixed(2)}</span>
        </div>

        <section class="card" style="margin-top:18px;">
          <h3 class="section-title">Condiciones generales</h3>
          <p class="preview-text"><strong>Forma de pago:</strong><br>${nl2br(appState.quotation.paymentTerms || "")}</p>
          <p class="preview-text"><strong>Observaciones:</strong><br>${nl2br(appState.quotation.notes || "")}</p>
        </section>

        <section class="footer-box">
          <div class="contact">
            <strong>BioSolutions</strong><br>
            Falsuri N° 155 entre Heroínas y Gral. Achá, Cochabamba - Bolivia<br>
            bio.solutions.bo@gmail.com<br>
            www.biosolutions.com.bo
          </div>
          <div class="sign">
            <div class="sign-line"></div>
            <strong>BioSolutions</strong><br>
            <span>Área Comercial</span>
          </div>
        </section>
      </div>
    </section>
  `;
}

function renderPreview() {
  const preview = document.getElementById("previewPages");
  if (!preview) return;

  const itemPages = appState.items.flatMap(item => buildItemPages(item)).join("");
  preview.innerHTML = itemPages + buildTotalPage();
}

function renderAll() {
  populateQuotationFields();
  renderItemsList();
  populateItemFields();
  renderEditors();
  renderPreview();
}

async function saveQuotationToDb() {
  const payload = {
    quotation: appState.quotation,
    items: appState.items,
    selectedItemId: appState.selectedItemId
  };

  const res = await fetch("/cotizaciones/guardar", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(payload)
  });

  const data = await res.json();

  if (data.ok) {
    appState.quotation.dbId = data.cotizacion_id;
    appState.quotation.number = data.numero || appState.quotation.number;
    document.getElementById("qNumber").value = appState.quotation.number;
    alert(`Cotización guardada: ${data.numero}`);
  } else {
    alert("No se pudo guardar la cotización.");
  }
}

async function loadQuotationFromDb(cotizacionId) {
  const res = await fetch(`/cotizaciones/${cotizacionId}/json`);
  const data = await res.json();

  if (data.error) {
    alert(data.error);
    return;
  }

  appState.quotation = data.quotation || appState.quotation;
  appState.items = data.items || [];
  appState.selectedItemId = data.selectedItemId || (appState.items[0]?.id ?? null);

  if (appState.items.length === 0) addItem();
  else renderAll();
}

function bindButtons() {
  const byId = (id) => document.getElementById(id);

  const newBtn = byId("newQuotationBtn");
  const saveQuotationBtn = byId("saveQuotationBtn");
  const addItemBtn = byId("addItemBtn");
  const addTemplateBtn = byId("addTemplateBtn");
  const templateSelect = byId("templateSelect");
  const duplicateBtn = byId("duplicateItemBtn");
  const deleteBtn = byId("deleteItemBtn");
  const printBtn = byId("printBtn");

  const addHighlightBtn = byId("addHighlightBtn");
  const addSpecBtn = byId("addSpecBtn");
  const addUseBtn = byId("addUseBtn");
  const addAccessoryBtn = byId("addAccessoryBtn");
  const addAdvantageBtn = byId("addAdvantageBtn");

  if (newBtn) {
    newBtn.onclick = (e) => {
      e.preventDefault();
      resetQuotation();
    };
  }

  if (saveQuotationBtn) {
    saveQuotationBtn.onclick = async (e) => {
      e.preventDefault();
      await saveQuotationToDb();
    };
  }

  if (addItemBtn) {
    addItemBtn.onclick = (e) => {
      e.preventDefault();
      addItem();
    };
  }

  if (addTemplateBtn && templateSelect) {
    addTemplateBtn.onclick = (e) => {
      e.preventDefault();
      if (!templateSelect.value) return;
      addItemFromTemplate(templateSelect.value);
      templateSelect.value = "";
    };
  }

  if (duplicateBtn) {
    duplicateBtn.onclick = (e) => {
      e.preventDefault();
      duplicateSelectedItem();
    };
  }

  if (deleteBtn) {
    deleteBtn.onclick = (e) => {
      e.preventDefault();
      deleteSelectedItem();
    };
  }

  if (printBtn) {
    printBtn.onclick = (e) => {
      e.preventDefault();
      window.print();
    };
  }

  if (addHighlightBtn) {
    addHighlightBtn.onclick = (e) => {
      e.preventDefault();
      const item = getSelectedItem();
      if (!item) return;
      item.highlights.push("Nueva característica");
      renderEditors();
      renderPreview();
    };
  }

  if (addSpecBtn) {
    addSpecBtn.onclick = (e) => {
      e.preventDefault();
      const item = getSelectedItem();
      if (!item) return;
      item.specs.push({ param: "Parámetro", value: "Detalle" });
      renderEditors();
      renderPreview();
    };
  }

  if (addUseBtn) {
    addUseBtn.onclick = (e) => {
      e.preventDefault();
      const item = getSelectedItem();
      if (!item) return;
      item.uses.push("Nuevo uso");
      renderEditors();
      renderPreview();
    };
  }

  if (addAccessoryBtn) {
    addAccessoryBtn.onclick = (e) => {
      e.preventDefault();
      const item = getSelectedItem();
      if (!item) return;
      item.accessories.push("Nuevo accesorio");
      renderEditors();
      renderPreview();
    };
  }

  if (addAdvantageBtn) {
    addAdvantageBtn.onclick = (e) => {
      e.preventDefault();
      const item = getSelectedItem();
      if (!item) return;
      item.advantages.push("Nueva ventaja");
      renderEditors();
      renderPreview();
    };
  }
}

async function init() {
  bindQuotationFields();
  bindItemMainFields();
  bindButtons();

  if (window.COTIZACION_ID && window.COTIZACION_ID !== "null") {
    await loadQuotationFromDb(window.COTIZACION_ID);
  } else {
    addItem();
  }
}

init();