import sqlite3, io, csv, os, shutil, uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string
from flask import request, redirect, Response, jsonify, send_from_directory, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "workshop_inventory_secret_key"
DB_FILE = "/opt/parts-db/inventory.db"
UPLOAD_FOLDER = "/opt/parts-db/images"
BACKUP_FOLDER = "/opt/parts-db/backups"
PROFILES_FOLDER = "/opt/parts-db/part_profiles"
app.config.update(UPLOAD_FOLDER=UPLOAD_FOLDER, PROFILES_FOLDER=PROFILES_FOLDER)

def get_phoenix_time():
    return datetime.now(ZoneInfo("America/Phoenix")).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT NOT NULL, part_name TEXT NOT NULL,
            category TEXT, quantity INTEGER DEFAULT 0, notes TEXT, purchase_url TEXT,
            image_filename TEXT, last_updated TEXT, profile_filename TEXT DEFAULT '',
            min_stock INTEGER DEFAULT 0
        )
    """)
    try: conn.execute("ALTER TABLE inventory ADD COLUMN profile_filename TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: conn.execute("ALTER TABLE inventory ADD COLUMN min_stock INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass
    conn.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, parent_name TEXT DEFAULT NULL
        )
    """)
    try: conn.execute("ALTER TABLE categories ADD COLUMN parent_name TEXT DEFAULT NULL")
    except sqlite3.OperationalError: pass
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone()[0] == 0:
        cats = [("Fasteners", None), ("Passive Electronics", None), ("Active Electronics", None),
                ("Hardware", None), ("Empty Bin", None), ("Screws", "Fasteners"),
                ("Resistors", "Passive Electronics"), ("Capacitors", "Passive Electronics")]
        for n, p in cats:
            try: conn.execute("INSERT INTO categories (name, parent_name) VALUES (?, ?)", (n, p))
            except: pass
    conn.commit()
    conn.close()

HTML_PAGE = """<!DOCTYPE html><html><head><title>Inventory</title><style>
body { font-family: sans-serif; max-width: 1150px; margin: 20px auto; padding: 0 15px; background: #f4f4f4; color: #333; }
.box { background: white; padding: 20px; border-radius: 5px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
.box-compact { background: white; padding: 14px; border-radius: 5px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); box-sizing: border-box; }
.box-compact h3 { margin-top: 0; margin-bottom: 8px; font-size: 15px; }
.box-compact p { margin: 0 0 8px 0; font-size: 13px; color: #444; }
input, select { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; font-size: 14px; }
.box-compact input, .box-compact select, .box-compact button { padding: 6px 10px; margin: 4px 0; font-size: 13px; }
button { padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
.s-btn { background: #007bff; }
.c-btn { background: #6c757d; text-decoration: none; color: white; padding: 8px 15px; border-radius: 4px; font-weight: bold; text-align: center; display: inline-block; font-size: 14px; box-sizing: border-box; }
.f-btn { background: #6c757d; color: white; margin-top: 5px; width: 100%; }
.e-btn { background: #17a2b8; color: white; text-decoration: none; padding: 6px 12px; float: right; border-radius: 4px; font-size: 13px; margin-left: 5px; font-weight: bold; }
.b-btn { background: #6f42c1; } .r-btn { background: #fd7e14; }
.del-btn { background: #dc3545; padding: 4px 8px; font-size: 12px; margin: 0; }
.save-btn { background: #28a745; padding: 4px 8px; font-size: 12px; margin: 0; }
.edit-lnk { color: #007bff; text-decoration: none; font-size: 13px; font-weight: bold; margin-right: 10px; }
.table-container { max-height: 550px; overflow-y: auto; border: 1px solid #ddd; border-radius: 4px; background: white; margin-top: 10px; position: relative; }
table { width: 100%; border-collapse: collapse; background: white; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; vertical-align: middle; }
th { background: #eee; position: sticky; top: 0; z-index: 10; box-shadow: 0 2px 2px -1px rgba(0,0,0,0.15); }
.row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
.row2 { display: grid; grid-template-columns: 2fr 1fr; gap: 8px; }
.row-search { display: grid; grid-template-columns: 3fr auto auto; gap: 8px; }
.grid-split { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.grid-three { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
.time-text { font-size: 11px; color: #666; font-family: monospace; }
.t-input { padding: 4px; margin: 0; font-size: 13px; width: 100%; }
.part-img { max-width: 60px; max-height: 60px; border-radius: 4px; border: 1px solid #ccc; display: block; object-fit: cover; }
.drop-zone { border: 2px dashed #999; padding: 12px; text-align: center; background: #fdfdfd; border-radius: 4px; cursor: pointer; margin-top: 5px; }
.drop-zone--over { border-color: #007bff; background: #e6f0fa; } .drop-zone__input { display: none; }
.drop-zone__prompt { font-size: 13px; color: #555; font-weight: bold; }
.modal { display: none; position: fixed; z-index: 100; left: 0; top: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); }
.modal-content { background: white; margin: 10% auto; padding: 20px; width: 60%; border-radius: 5px; max-height: 60vh; overflow-y: auto; }
.img-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); gap: 10px; margin-top: 15px; }
.img-grid img { width: 100%; height: 80px; object-fit: cover; border: 2px solid #ccc; border-radius: 4px; cursor: pointer; }
.btn-container { display: flex; justify-content: space-between; margin-top: 10px; } .clr-btn { background: #6c757d; }
.sort-link { text-decoration: none; color: #333; font-weight: bold; }
.sort-arrow { font-size: 12px; margin-left: 3px; display: inline-block; vertical-align: middle; }
.sort-arrow.active { color: #007bff; font-weight: bold; }
.flash-msg { padding: 10px; background: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; margin-bottom: 12px; font-weight: bold; font-size: 14px; }
.meter-text { font-size: 11px; font-family: monospace; color: #666; background: #eee; padding: 2px 4px; border-radius: 3px; display: inline-block; margin-top: 2px; }
.audit-item { font-size: 12px; margin: 2px 0; padding: 2px 6px; border-radius: 3px; background: #f8d7da; color: #721c24; font-family: monospace; }
.audit-good { background: #d4edda; color: #155724; }
.bulk-bar { display: none; align-items: center; justify-content: space-between; gap: 10px; background: #e2e3e5; padding: 10px; border-radius: 4px; margin-bottom: 10px; border: 1px solid #d6d8db; }
.bulk-title { font-weight: bold; font-size: 14px; color: #383d41; }
.bulk-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.bulk-actions select, .bulk-actions input { width: auto; max-width: 180px; padding: 4px 8px; font-size: 13px; margin: 0; }
.bulk-actions button { padding: 5px 12px; font-size: 13px; margin: 0; }
</style>
"""
HTML_JS = """<script>
let currentTargetField = 'selected_existing_image';
let currentPromptField = '.drop-zone__prompt';
let currentPreviewImgId = null;

function setMode(mode){
    document.getElementById("d_row").style.display = mode === "drawer" ? "grid" : "none";
    document.getElementById("s_row").style.display = mode === "shelf" ? "block" : "none";
}
function openImageModal(targetInputId, promptClass, previewImgId, apiEndpoint, pathPrefix){
    currentTargetField = targetInputId;
    currentPromptField = promptClass;
    currentPreviewImgId = previewImgId;
    document.getElementById("imgModal").style.display = "block";
    fetch(apiEndpoint).then(r => r.json()).then(images => {
        const grid = document.getElementById("modalImgGrid"); grid.innerHTML = "";
        images.forEach(img => {
            const el = document.createElement("img"); el.src = pathPrefix + img;
            el.onclick = () => { 
                document.getElementById(currentTargetField).value = img; 
                const promptEl = document.querySelector(currentPromptField);
                if(promptEl) promptEl.textContent = "Selected: " + img; 
                if(currentPreviewImgId) {
                    document.getElementById(currentPreviewImgId).src = pathPrefix + img;
                    document.getElementById(currentPreviewImgId).style.display = "block";
                }
                const clearFlag = document.getElementById(currentTargetField.replace('edit_existing_image_', 'clear_image_flag_').replace('edit_existing_profile_', 'clear_profile_flag_'));
                if(clearFlag) clearFlag.value = "0";
                closeImageModal(); 
            };
            grid.appendChild(el);
        });
    });
}
function closeImageModal(){ document.getElementById("imgModal").style.display = "none"; }
function handleEditFileChange(input, previewId, flagId) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const img = document.getElementById(previewId);
            img.src = e.target.result;
            img.style.display = "block";
        };
        reader.readAsDataURL(input.files[0]);
        const clearFlag = document.getElementById(flagId);
        if(clearFlag) clearFlag.value = "0";
    }
}
function confirmClearAction(previewId, hiddenInputId, flagId, promptId, message) {
    if(confirm(message)) { clearEditImage(previewId, hiddenInputId, flagId, promptId); }
}
function clearEditImage(previewId, hiddenInputId, flagId, promptId) {
    const img = document.getElementById(previewId);
    if(img) { img.src = ""; img.style.display = "none"; }
    const fileInput = img ? img.nextElementSibling : null;
    if(fileInput && fileInput.type === 'file') fileInput.value = "";
    const hiddenInp = document.getElementById(hiddenInputId);
    if(hiddenInp) hiddenInp.value = "";
    const clearFlag = document.getElementById(flagId);
    if(clearFlag) clearFlag.value = "1";
    const promptEl = document.querySelector(promptId);
    if(promptEl) promptEl.textContent = "Cleared";
}
function clearManualForm(){
    document.getElementById("manualPartForm").reset(); setMode("unassigned");
    document.getElementById("selected_existing_image").value = "";
    document.querySelector(".drop-zone__prompt").textContent = "Drag & Drop Image Here or Click to Browse";
}
function toggleAllRows(masterCheckbox) {
    const checkboxes = document.querySelectorAll(".row-select-checkbox");
    checkboxes.forEach(cb => cb.checked = masterCheckbox.checked);
    updateBulkBarState();
}
function onRowCheckboxChange() {
    const master = document.getElementById("masterSelectCheckbox");
    const checkboxes = document.querySelectorAll(".row-select-checkbox");
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    if(master) master.checked = checkboxes.length > 0 && allChecked;
    updateBulkBarState();
}
function updateBulkBarState() {
    const checkboxes = document.querySelectorAll(".row-select-checkbox:checked");
    const bar = document.getElementById("bulkActionBar");
    const countLabel = document.getElementById("bulkSelectCount");
    if (!bar) return;
    if (checkboxes.length > 0) {
        bar.style.display = "flex";
        if(countLabel) countLabel.textContent = checkboxes.length;
    } else { bar.style.display = "none"; }
}
function submitBulkForm(actionType) {
    const checkboxes = document.querySelectorAll(".row-select-checkbox:checked");
    if(checkboxes.length === 0) return;
    if(actionType === 'delete' && !confirm(`Verification: Are you sure you want to permanently delete all ${checkboxes.length} selected items?`)) { return; }
    const itemIds = Array.from(checkboxes).map(cb => cb.value);
    document.getElementById("bulkItemIdsHidden").value = itemIds.join(",");
    document.getElementById("bulkActionTypeHidden").value = actionType;
    if(actionType === 'category') { document.getElementById("bulkActionValueHidden").value = document.getElementById("bulkCategorySelect").value; }
    document.getElementById("bulkActionFormForm").submit();
}
document.addEventListener("DOMContentLoaded", () => {
    const dropZone = document.getElementById("image-drop-zone"), fileInput = document.getElementById("part_image_input");
    if (!dropZone) return;
    dropZone.addEventListener("click", (e) => { if(e.target.tagName !== 'BUTTON') fileInput.click(); });
    fileInput.addEventListener("change", () => { if(fileInput.files.length) { dropZone.querySelector(".drop-zone__prompt").textContent = "Selected: " + fileInput.files[0].name; document.getElementById("selected_existing_image").value = ""; } });
    dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drop-zone--over"); });
    ["dragleave", "dragend"].forEach(t => dropZone.addEventListener(t, () => dropZone.classList.remove("drop-zone--over")));
    dropZone.addEventListener("drop", (e) => {
        e.preventDefault(); dropZone.classList.remove("drop-zone--over");
        if (e.dataTransfer.files.length) { fileInput.files = e.dataTransfer.files; dropZone.querySelector(".drop-zone__prompt").textContent = "Selected: " + e.dataTransfer.files[0].name; document.getElementById("selected_existing_image").value = ""; }
    });
});
</script></head>"""
HTML_BODY_FORM = """<body><h2>🛠️ Workshop Inventory Engine</h2>
{% with messages = get_flashed_messages() %}
  {% if messages %}
    {% for message in messages %}
      <div class="flash-msg">{{ message }}</div>
    {% endfor %}
  {% endif %}
{% endwith %}
<div class="box"><h3>Add New Part Manually</h3>
<form action="/add" id="manualPartForm" method="POST" enctype="multipart/form-data">
    <div style="margin-bottom:10px;">
        <input type="radio" name="loc_type" value="unassigned" checked onclick="setMode('unassigned')" style="width:auto;"> <b style="color:#007bff;">Unassigned Mode</b> &nbsp;&nbsp;
        <input type="radio" name="loc_type" value="drawer" onclick="setMode('drawer')" style="width:auto;"> <b>Drawer Mode (1-35)</b> &nbsp;&nbsp;
        <input type="radio" name="loc_type" value="shelf" onclick="setMode('shelf')" style="width:auto;"> <b>Freeform Shelf Mode</b>
    </div>
    <div id="d_row" class="row3" style="display:none;">
        <select name="drawer">{% for d in range(1, 36) %}<option value="D{{ d }}">Drawer {{ d }}</option>{% endfor %}</select>
        <select name="row_letter">{% for r in ['A','B','C','D','E','F','G','H'] %}<option value="{{ r }}">Row {{ r }}</option>{% endfor %}</select>
        <select name="col_num">{% for c in range(1, 10) %}<option value="{{ c }}">Col {{ c }}</option>{% endfor %}</select>
    </div>
    <div id="s_row" style="display:none;"><input type="text" name="shelf_name" placeholder="Type custom location name (e.g., SHELF-A, BACK-WALL, WORKBENCH)"></div>
    <div class="row3" style="margin-top:10px;">
        <input type="text" name="part_name" placeholder="Part Name" required>
        <select name="category"><option value="None" selected>None</option>
            {% for cat in categories %}<option value="{{ cat.name }}森林">{% if cat.parent_name %}{{ cat.parent_name }} &gt; {% endif %}{{ cat.name }}</option>{% endfor %}
        </select>
        <select name="initial_profile"><option value="">-- Choose Profile Image (Optional) --</option>
            {% for p_img in profile_list %}<option value="{{ p_img }}">{{ p_img }}</option>{% endfor %}
        </select>
    </div>
    <div class="grid-three">
        <input type="number" name="quantity" value="0" min="0" placeholder="Qty">
        <input type="number" name="min_stock" value="0" min="0" placeholder="Low Stock Level Threshold (Optional)">
        <input type="text" name="purchase_url" placeholder="Paste Purchase Link URL (optional)">
    </div>
    <div class="row2" style="margin-top: 10px;"><input type="text" name="notes" placeholder="Notes (optional)">
        <div><div id="image-drop-zone" class="drop-zone"><span class="drop-zone__prompt">Drag & Drop Image Here or Click to Browse</span><input type="file" name="part_image" id="part_image_input" class="drop-zone__input" accept="image/*"></div>
            <input type="hidden" name="selected_existing_image" id="selected_existing_image" value=""><button type="button" onclick="openImageModal('selected_existing_image', '.drop-zone__prompt', null, '/api/list_images', '/images/')" style="margin-top:5px; width:100%; background:#17a2b8;">Browse Existing Images</button>
        </div>
    </div>
    <div class="btn-container"><button type="submit">Save Part</button><button type="button" class="clr-btn" onclick="clearManualForm()">Clear</button></div>
</form></div>
<div id="imgModal" class="modal"><div class="modal-content"><span style="float:right; cursor:pointer; font-weight:bold; font-size:20px;" onclick="closeImageModal()">&times;</span><h4>Select Gallery Image</h4><div id="modalImgGrid" class="img-grid"></div></div></div>"""
HTML_TAIL = """<div class="box-compact" style="background: #eef1f6;">
    <div class="grid-three">
        <div><h3>📁 Bulk Profile Upload</h3><form action="/upload_to_parts_images" method="POST" enctype="multipart/form-data"><input type="file" name="parts_files" multiple required style="background:white; padding:3px; margin-bottom:4px; width:100%; font-size:12px;"><button type="submit" style="background:#28a745; width:100%; font-size:12px; padding:5px 8px;">Upload to part_profiles</button></form></div>
        <div><h3>📷 Bulk Image Upload</h3><form action="/upload_to_images" method="POST" enctype="multipart/form-data"><input type="file" name="images_files" multiple accept="image/*" required style="background:white; padding:3px; margin-bottom:4px; width:100%; font-size:12px;"><button type="submit" style="background:#17a2b8; width:100%; font-size:12px; padding:5px 8px;">Upload to images</button></form></div>
        <div style="display: flex; flex-direction: column; justify-content: space-between;">
            <div><h3>🧹 System Storage Clean</h3>
                <p style="font-size:12px; margin:0 0 2px 0; color:#555; line-height:1.2;">Purge unreferenced image assets from storage disk.</p>
                <div class="meter-text">Usage: {{ storage_stats['count'] }} imgs / {{ storage_stats['size'] }} MB</div>
            </div>
            <form action="/cleanup_orphaned_images" method="POST" onsubmit="return confirm('Verification: Are you sure you want to permanently purge all unreferenced image assets?');"><button type="submit" style="background:#dc3545; width:100%; font-size:12px; padding:5px 8px; margin:0;">Clean Orphaned Images</button></form>
        </div>
    </div>
</div>
<div class="box-compact" style="background: #e8f4fd;"><h3>📊 Database CSV Exchange & Integrity Verification</h3>
    <div class="grid-split">
        <div>
            <form action="/import" method="POST" enctype="multipart/form-data" style="display:flex; gap:8px; align-items:center; margin-bottom: 6px;"><input type="file" name="csv_file" accept=".csv" required style="background:white; padding:3px; margin:0; font-size:12px; flex-grow:1;"><button type="submit" style="background:#007bff; font-size:12px; padding:5px 12px; margin:0; white-space:nowrap;">Upload CSV</button></form>
            <div style="display:flex; align-items:center;"><a href="/export" style="background:#6f42c1; color:white; text-decoration:none; padding:5px 12px; border-radius:4px; font-weight:bold; text-align:center; width:100%; font-size:12px; box-sizing:border-box;">📥 Download Database CSV</a></div>
        </div>
        <div style="border-left: 1px solid #b8daff; padding-left: 12px;">
            <h4 style="margin: 0 0 4px 0; font-size: 13px;">🔍 Integrity Diagnostic Audit</h4>
            <div class="audit-item {% if audit_stats['unassigned'] == 0 %}audit-good{% endif %}">⚠️ Unassigned Storage Spots: {{ audit_stats['unassigned'] }}</div>
            <div class="audit-item {% if audit_stats['no_type'] == 0 %}audit-good{% endif %}">⚠️ Items Missing Type: {{ audit_stats['no_type'] }}</div>
        </div>
    </div>
</div>
<div class="grid-split">
    <div class="box-compact" style="background: #fff3cd; border: 1px solid #ffeeba;"><h3>📥 Category CSV Transfer</h3>
        <form action="/import_categories_csv" method="POST" enctype="multipart/form-data" style="display:flex; flex-direction:column; gap:4px; margin-bottom:5px;"><input type="file" name="cat_csv_file" accept=".csv" required style="background:white; padding:3px; margin:0; font-size:12px;"><button type="submit" style="background:#ffc107; color:#212529; width:100%; font-size:12px; padding:4px 8px; font-weight:bold; border:none; border-radius:3px;">Upload Categories CSV</button></form>
        <a href="/export_categories_csv" style="background:#17a2b8; color:white; text-decoration:none; padding:5px 8px; border-radius:4px; font-weight:bold; text-align:center; display:block; font-size:12px; box-sizing:border-box;">📤 Download Categories CSV</a>
    </div>
    <div class="box-compact" style="background: #fff3cd; border: 1px solid #ffeeba;"><h3>➕ Add Custom Item Type</h3>
        <form action="/add_cat" method="POST" style="display:flex; flex-direction:column; gap:4px;"><input type="text" name="new_cat" placeholder="New category name..." required style="margin:0; font-size:13px;"><select name="parent_cat" style="margin:0; font-size:13px;"><option value="" selected>No Parent (Top-Level)</option>{% for cat in categories %}<option value="{{ cat.name }}森林">{{ cat.name }}</option>{% endfor %}</select><button type="submit" style="background:#6c757d; margin:0; font-weight:bold; padding:4px 8px;">Add Type</button></form>
    </div>
</div>"""
HTML_TABLE_BOX = """<div class="box" id="search-box">
<a href="/restore_db" class="e-btn r-btn" onclick="return confirm('Verification: Are you sure you want to overwrite your active database data with your saved backup file?');">🔄 Restore Backup</a><a href="/backup_db" class="e-btn b-btn">💾 Save Backup</a><h3>Search Inventory</h3>
<form action="/#search-box" method="GET" style="margin-bottom:15px;">
    <div class="row-search">
        <input type="text" name="q" value="{{ query }}" placeholder="Search name...">
        <button type="submit" class="s-btn">Search</button>
        {% if query %}<a href="/#search-box" class="c-btn">Clear</a>{% endif %}
    </div>
    <div style="margin-top: 10px; display: grid; grid-template-columns: 2fr 1fr; gap: 8px;">
        <select name="sort_by">
            <option value="last_updated" {% if sort_by == 'last_updated' %}selected{% endif %}>Last Updated</option>
            <option value="location" {% if sort_by == 'location' %}selected{% endif %}>Location</option>
            <option value="part_name" {% if sort_by == 'part_name' %}selected{% endif %}>Name & Details</option>
            <option value="category" {% if sort_by == 'category' %}selected{% endif %}>Type</option>
        </select>
        <input type="hidden" name="direction" value="{{ direction }}">
        <button type="submit" class="f-btn" style="margin:0;">Filter</button>
    </div>
</form>

<div class="bulk-bar" id="bulkActionBar">
    <div class="bulk-title">📦 Bulk Actions Selected (<span id="bulkSelectCount">0</span> items)</div>
    <div class="bulk-actions">
        <select id="bulkCategorySelect">
            <option value="None">None</option>
            {% for c in categories %}<option value="{{ c.name }}森林">{{ c.name }}</option>{% endfor %}
        </select>
        <button type="button" style="background: #17a2b8;" onclick="submitBulkForm('category')">Assign Type</button>
        <button type="button" style="background: #dc3545;" onclick="submitBulkForm('delete')">Mass Delete</button>
    </div>
</div>

<form id="bulkActionFormForm" action="/bulk_operation" method="POST" style="display:none;">
    <input type="hidden" name="item_ids" id="bulkItemIdsHidden" value="">
    <input type="hidden" name="action_type" id="bulkActionTypeHidden" value="">
    <input type="hidden" name="action_value" id="bulkActionValueHidden" value="">
</form>

<div class="table-container">
<table><thead><tr>
<th style="width:4%; text-align:center;"><input type="checkbox" id="masterSelectCheckbox" onclick="toggleAllRows(this)" style="margin:0; width:auto; cursor:pointer;"></th>
<th style="width:10%;">Photo</th>
<th style="width:14%;"><a class="sort-link" href="?q={{ query }}&sort_by=location&direction={% if sort_by == 'location' and direction == 'asc' %}desc{% else %}asc{% endif %}#search-box">Location<span class="sort-arrow {% if sort_by == 'location' %}active{% endif %}">{% if sort_by == 'location' and direction == 'desc' %}▼{% else %}▲{% endif %}</span></a></th>
<th style="width:12%;">Profile</th>
<th style="width:34%;"><a class="sort-link" href="?q={{ query }}&sort_by=part_name&direction={% if sort_by == 'part_name' and direction == 'asc' %}desc{% else %}asc{% endif %}#search-box">Name & Details<span class="sort-arrow {% if sort_by == 'part_name' %}active{% endif %}">{% if sort_by == 'part_name' and direction == 'desc' %}▼{% else %}▲{% endif %}</span></a></th>
<th style="width:14%;"><a class="sort-link" href="?q={{ query }}&sort_by=category&direction={% if sort_by == 'category' and direction == 'asc' %}desc{% else %}asc{% endif %}#search-box">Type<span class="sort-arrow {% if sort_by == 'category' %}active{% endif %}">{% if sort_by == 'category' and direction == 'desc' %}▼{% else %}▲{% endif %}</span></a></th>
<th style="width:12%;"><a class="sort-link" href="?q={{ query }}&sort_by=last_updated&direction={% if sort_by == 'last_updated' and direction == 'asc' %}desc{% else %}asc{% endif %}#search-box">Updated<span class="sort-arrow {% if sort_by == 'last_updated' %}active{% endif %}">{% if sort_by == 'last_updated' and direction == 'desc' %}▼{% else %}▲{% endif %}</span></a></th>
<th style="width:10%;">Actions</th></tr></thead><tbody>
"""
HTML_TABLE_LOOP = """{% for item_id, loc, name, cat, qty, notes, p_url, img, ts, prof, min_s in items %}<tr>
<td style="text-align:center;"><input type="checkbox" class="row-select-checkbox" value="{{ item_id }}" onclick="onRowCheckboxChange()" style="margin:0; width:auto; cursor:pointer;"></td>
{% if edit_id == item_id %}<form action="/update/{{ item_id }}" method="POST" enctype="multipart/form-data">
<td><img id="preview_{{ item_id }}" src="{% if img %}/images/{{ img }}{% endif %}" class="part-img" style="margin-bottom:4px; {% if not img %}display:none;{% endif %}"><input type="file" name="part_image" accept="image/*" style="font-size:11px; max-width:90px;" onchange="handleEditFileChange(this, 'preview_{{ item_id }}', 'clear_image_flag_{{ item_id }}')"><br><button type="button" onclick="openImageModal('edit_existing_image_{{ item_id }}', '#prompt_{{ item_id }}', 'preview_{{ item_id }}', '/api/list_images', '/images/')" style="font-size:10px; padding:2px 4px; background:#17a2b8; width:100%; margin-top:2px;">Gallery</button><input type="hidden" name="selected_existing_image" id="edit_existing_image_{{ item_id }}" value=""><input type="hidden" name="clear_image_flag" id="clear_image_flag_{{ item_id }}" value="0"><button type="button" onclick="confirmClearAction('preview_{{ item_id }}', 'edit_existing_image_{{ item_id }}', 'clear_image_flag_{{ item_id }}', '#prompt_{{ item_id }}', 'Verification: Are you sure you want to completely remove this photo asset attachment?')" style="font-size:10px; padding:2px 4px; background:#dc3545; color:white; width:100%; margin-top:2px; border:none; border-radius:3px; cursor:pointer; font-weight:bold;">Remove Photo</button><div id="prompt_{{ item_id }}" style="font-size:9px; color:#555; overflow:hidden; text-overflow:ellipsis; max-width:90px; margin-top:2px;"></div></td>
<td><input type="text" name="location" value="{{ loc }}" class="t-input" required></td>
<td><img id="preview_prof_{{ item_id }}" src="{% if prof %}/parts_images/{{ prof }}{% endif %}" class="part-img" style="margin-bottom:4px; {% if not prof %}display:none;{% endif %}"><input type="file" name="profile_image" accept="image/*" style="font-size:11px; max-width:90px;" onchange="handleEditFileChange(this, 'preview_prof_{{ item_id }}', 'clear_profile_flag_{{ item_id }}')"><br><button type="button" onclick="openImageModal('edit_existing_profile_{{ item_id }}', '#prompt_prof_{{ item_id }}', 'preview_prof_{{ item_id }}', '/api/list_profile_images', '/parts_images/')" style="font-size:10px; padding:2px 4px; background:#17a2b8; width:100%; margin-top:2px;">Gallery</button><input type="hidden" name="selected_existing_profile" id="edit_existing_profile_{{ item_id }}" value=""><input type="hidden" name="clear_profile_flag" id="clear_profile_flag_{{ item_id }}" value="0"><button type="button" onclick="confirmClearAction('preview_prof_{{ item_id }}', 'edit_existing_profile_{{ item_id }}', 'clear_profile_flag_{{ item_id }}', '#prompt_prof_{{ item_id }}', 'Verification: Are you sure you want to completely remove this profile image asset mapping?')" style="font-size:10px; padding:2px 4px; background:#dc3545; color:white; width:100%; margin-top:2px; border:none; border-radius:3px; cursor:pointer; font-weight:bold;">Remove Profile</button><div id="prompt_prof_{{ item_id }}" style="font-size:9px; color:#555; overflow:hidden; text-overflow:ellipsis; max-width:90px; margin-top:2px;"></div></td>
<td><input type="text" name="part_name" value="{{ name }}" class="t-input" required><br><input type="text" name="notes" value="{{ notes }}" class="t-input" placeholder="Notes"><br><input type="text" name="purchase_url" value="{{ p_url }}" class="t-input" placeholder="Purchase URL"><input type="hidden" name="quantity" value="{{ qty }}"><input type="hidden" name="min_stock" value="{{ min_s }}"></td>
<td><select name="category" class="t-input"><option value="None" {% if cat == 'None' %}selected{% endif %}>None</option>{% for c in categories %}<option value="{{ c.name }}" {% if c.name == cat %}selected{% endif %}>{% if c.parent_name %}{{ c.parent_name }} &gt; {% endif %}{{ c.name }}</option>{% endfor %}</select></td><td class="time-text">{{ ts[:10] }}</td><td><button type="submit" class="save-btn">Save</button> <a href="?q={{ query }}&sort_by={{ sort_by }}&direction={{ direction }}#search-box" class="edit-lnk" style="color:#666; margin-left:5px;">Cancel</a></td></form>
{% else %}<td>{% if img %}<img src="/images/{{ img }}" class="part-img">{% else %}<span style="color:#ccc; font-size:11px;">No Photo</span>{% endif %}</td><td><b>{{ loc }}</b></td><td>{% if prof %}<img src="/parts_images/{{ prof }}" class="part-img">{% else %}<span style="color:#ccc; font-size:11px;">No Profile</span>{% endif %}</td><td>{{ name }}<br><small style="color:#777;">{{ notes }}</small>{% if p_url %}<br><a href="{{ p_url }}" target="_blank" class="buy-link">🔗 Buy Link</a>{% endif %}</td>
<td>{{ cat }}</td><td class="time-text">{{ ts[:10] }}</td><td><a href="?edit={{ item_id }}&q={{ query }}&sort_by={{ sort_by }}&direction={{ direction }}#search-box" class="edit-lnk">Edit</a><form action="/delete/{{ item_id }}" method="POST" style="display:inline;" onsubmit="return confirm('Verification: Are you sure you want to permanently delete this part record?');"><button type="submit" class="del-btn">Delete</button></form></td>{% endif %}</tr>
{% else %}<tr><td colspan="8" style="text-align:center; color:#777;">No items found</td></tr>{% endfor %}</tbody></table></div></div></body></html>"""

@app.route("/images/<filename>")
def get_image(filename): return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/parts_images/<filename>")
def get_parts_image(filename): return send_from_directory(app.config['PROFILES_FOLDER'], filename)

@app.route("/api/list_images")
def list_images():
    files = os.listdir(app.config['UPLOAD_FOLDER'])
    return jsonify(sorted([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))]))
@app.route("/api/list_profile_images")
def list_profile_images():
    if not os.path.exists(app.config['PROFILES_FOLDER']): return jsonify([])
    files = os.listdir(app.config['PROFILES_FOLDER'])
    return jsonify(sorted([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))]))

def get_disk_stats():
    total_size = 0
    total_count = 0
    for path in [UPLOAD_FOLDER, PROFILES_FOLDER]:
        if os.path.exists(path):
            for f in os.listdir(path):
                fp = os.path.join(path, f)
                if os.path.isfile(fp) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                    total_count += 1
                    total_size += os.path.getsize(fp)
    size_mb = round(total_size / (1024 * 1024), 2)
    return {"count": total_count, "size": size_mb}

def get_audit_stats():
    conn = sqlite3.connect(DB_FILE)
    unassigned = conn.execute("SELECT COUNT(*) FROM inventory WHERE location = 'UNASSIGNED' OR location = ''").fetchone()[0]
    no_type = conn.execute("SELECT COUNT(*) FROM inventory WHERE category = 'None' OR category IS NULL").fetchone()[0]
    conn.close()
    return {"unassigned": unassigned, "no_type": no_type}

@app.route("/")
def index():
    q, edit_id = request.args.get("q", "").strip(), request.args.get("edit", type=int)
    sort_by = request.args.get("sort_by", "last_updated").strip()
    direction = request.args.get("direction", "desc").strip().lower()
    
    if sort_by not in ["last_updated", "location", "part_name", "category"]:
        sort_by = "last_updated"
    if direction not in ["asc", "desc"]:
        direction = "desc" if sort_by == "last_updated" else "asc"
    
    order_dir = "ASC" if direction == "asc" else "DESC"
    order_clause = f"ORDER BY {sort_by} {order_dir}"

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name, parent_name FROM categories ORDER BY CASE WHEN parent_name IS NULL THEN name ELSE parent_name END, name")
    categories = [{"name": row[0], "parent_name": row[1]} for row in cur.fetchall()]
    
    if q:
        items = conn.execute(f"SELECT id, location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated, profile_filename, min_stock FROM inventory WHERE part_name LIKE ? OR location LIKE ? OR category LIKE ? OR notes LIKE ? {order_clause}", (f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        items = conn.execute(f"SELECT id, location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated, profile_filename, min_stock FROM inventory {order_clause}").fetchall()
    conn.close()
    
    profile_list = []
    if os.path.exists(PROFILES_FOLDER):
        profile_list = sorted([f for f in os.listdir(PROFILES_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'))])
        
    storage_stats = get_disk_stats()
    audit_stats = get_audit_stats()
    
    full_html = HTML_PAGE + HTML_JS + HTML_BODY_FORM + HTML_TAIL + HTML_TABLE_BOX + HTML_TABLE_LOOP
    return render_template_string(full_html, items=items, query=q, categories=categories, edit_id=edit_id, sort_by=sort_by, direction=direction, profile_list=profile_list, storage_stats=storage_stats, audit_stats=audit_stats)
@app.route("/backup_db")
def backup_db():
    if os.path.exists(DB_FILE): shutil.copy(DB_FILE, os.path.join(BACKUP_FOLDER, "inventory_backup.db"))
    return redirect("/#search-box")

@app.route("/restore_db")
def restore_db():
    src = os.path.join(BACKUP_FOLDER, "inventory_backup.db")
    if os.path.exists(src): shutil.copy(src, DB_FILE)
    return redirect("/#search-box")

@app.route("/add", methods=["POST"])
def add():
    mode = request.form.get("loc_type")
    if mode == "unassigned": loc = "UNASSIGNED"
    elif mode == "shelf": loc = request.form.get("shelf_name", "").strip().upper() or "SHELF"
    else: loc = f"{request.form.get('drawer')}-{request.form.get('row_letter')}{request.form.get('col_num')}"
    
    name = request.form.get('part_name').strip()
    cat = request.form.get('category')
    qty = int(request.form.get('quantity', 0))
    min_s = int(request.form.get('min_stock', 0))
    notes = request.form.get('notes').strip()
    p_url = request.form.get('purchase_url', '').strip()
    
    ts = get_phoenix_time()
    img_file = request.files.get('part_image')
    img_name = request.form.get('selected_existing_image', '').strip()
    init_prof = request.form.get('initial_profile', '').strip()
    
    if img_file and img_file.filename != "":
        secure_name = secure_filename(img_file.filename)
        ext = os.path.splitext(secure_name)[1]
        img_name = f"{uuid.uuid4().hex}{ext}"
        img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))
        
    conn = sqlite3.connect(DB_FILE)
    existing = conn.execute("SELECT id, quantity FROM inventory WHERE location = ? AND part_name = ?", (loc, name)).fetchone()
    if existing: 
        new_qty = existing[1] + qty
        conn.execute("UPDATE inventory SET category = ?, quantity = ?, min_stock = ?, notes = ?, purchase_url = ?, last_updated = ? WHERE id = ?", (cat, new_qty, min_s, notes, p_url, ts, existing[0]))
    else: 
        conn.execute("INSERT INTO inventory (location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated, profile_filename, min_stock) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (loc, name, cat, qty, notes, p_url, img_name, ts, init_prof, min_s))
    conn.commit(); conn.close()
    return redirect("/#search-box")
@app.route("/update/<int:item_id>", methods=["POST"])
def update_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    img_file = request.files.get('part_image')
    img_name = request.form.get('selected_existing_image', '').strip()
    clear_image = request.form.get('clear_image_flag', '0').strip()
    if clear_image == "1":
        conn.execute("UPDATE inventory SET image_filename = '' WHERE id = ?", (item_id,))
    elif img_file and img_file.filename != "":
        secure_name = secure_filename(img_file.filename)
        ext = os.path.splitext(secure_name)[1]
        img_name = f"{uuid.uuid4().hex}{ext}"
        img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))
        conn.execute("UPDATE inventory SET image_filename = ? WHERE id = ?", (img_name, item_id))
    elif img_name != "":
        conn.execute("UPDATE inventory SET image_filename = ? WHERE id = ?", (img_name, item_id))
        
    prof_file = request.files.get('profile_image')
    prof_name = request.form.get('selected_existing_profile', '').strip()
    clear_prof = request.form.get('clear_profile_flag', '0').strip()
    if clear_prof == "1":
        conn.execute("UPDATE inventory SET profile_filename = '' WHERE id = ?", (item_id,))
    elif prof_file and prof_file.filename != "":
        secure_name = secure_filename(prof_file.filename)
        ext = os.path.splitext(secure_name)[1]
        prof_name = f"{uuid.uuid4().hex}{ext}"
        prof_file.save(os.path.join(app.config['PROFILES_FOLDER'], prof_name))
        conn.execute("UPDATE inventory SET profile_filename = ? WHERE id = ?", (prof_name, item_id))
    elif prof_name != "":
        conn.execute("UPDATE inventory SET profile_filename = ? WHERE id = ?", (prof_name, item_id))

    conn.execute("UPDATE inventory SET location = ?, part_name = ?, category = ?, quantity = ?, min_stock = ?, notes = ?, purchase_url = ?, last_updated = ? WHERE id = ?", (request.form.get('location').strip().upper(), request.form.get('part_name').strip(), request.form.get('category'), int(request.form.get('quantity', 0)), int(request.form.get('min_stock', 0)), request.form.get('notes').strip(), request.form.get('purchase_url', '').strip(), get_phoenix_time(), item_id))
    conn.commit(); conn.close()
    return redirect("/#search-box")
@app.route("/bulk_operation", methods=["POST"])
def bulk_operation():
    ids_str = request.form.get("item_ids", "").strip()
    action = request.form.get("action_type", "").strip()
    val = request.form.get("action_value", "").strip()
    
    if not ids_str: return redirect("/#search-box")
    try: ids = [int(i) for i in ids_str.split(",") if i]
    except: return redirect("/#search-box")
    
    conn = sqlite3.connect(DB_FILE)
    ts = get_phoenix_time()
    if action == "delete":
        placeholders = ",".join(["?"] * len(ids))
        conn.execute(f"DELETE FROM inventory WHERE id IN ({placeholders})", ids)
        flash(f"Successfully deleted {len(ids)} components from the database.")
    elif action == "category":
        for i in ids:
            conn.execute("UPDATE inventory SET category = ?, last_updated = ? WHERE id = ?", (val, ts, i))
        flash(f"Successfully remapped types for {len(ids)} items.")
        
    conn.commit(); conn.close()
    return redirect("/#search-box")

@app.route("/upload_to_parts_images", methods=["POST"])
def upload_to_parts_images():
    for f in request.files.getlist("parts_files"):
        if f and f.filename != "": f.save(os.path.join(app.config['PROFILES_FOLDER'], secure_filename(f.filename)))
    return redirect("/")

@app.route("/upload_to_images", methods=["POST"])
def upload_to_images():
    for f in request.files.getlist("images_files"):
        if f and f.filename != "": f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
    return redirect("/")
@app.route("/import", methods=["POST"])
def import_csv():
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith('.csv'): return redirect("/#search-box")
    reader = csv.reader(io.StringIO(file.stream.read().decode("UTF-8"), newline=None))
    ts, conn = get_phoenix_time(), sqlite3.connect(DB_FILE)
    for r in reader:
        if not r or len(r) < 4 or "Location" in r or "part_name" in r: continue
        loc, name, cat = r[0].strip().upper(), r[1].strip(), r[2].strip()
        try: qty = int(r[3].strip() or 0)
        except: qty = 0
        notes = r[4].strip() if len(r) > 4 else ""
        p_url = r[5].strip() if len(r) > 5 else ""
        existing = conn.execute("SELECT id, quantity FROM inventory WHERE location = ? AND part_name = ?", (loc, name)).fetchone()
        if existing: 
            new_qty = existing[1] + qty
            conn.execute("UPDATE inventory SET category = ?, quantity = ?, notes = ?, purchase_url = ?, last_updated = ? WHERE id = ?", (cat, new_qty, notes, p_url, ts, existing[0]))
        else: 
            conn.execute("INSERT INTO inventory (location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated, profile_filename, min_stock) VALUES (?, ?, ?, ?, ?, ?, '', ?, '', 0)", (loc, name, cat, qty, notes, p_url, ts))
    conn.commit(); conn.close()
    return redirect("/#search-box")

@app.route("/adjust/<int:item_id>/<string:direction>")
def adjust(item_id, direction):
    amt = 1 if direction == "plus" else -1
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE inventory SET quantity = MAX(0, quantity + ?), last_updated = ? WHERE id = ?", (amt, get_phoenix_time(), item_id))
    conn.commit(); conn.close()
    return redirect(f"/?q={request.args.get('q', '')}&sort_by={request.args.get('sort_by', 'last_updated')}&direction={request.args.get('direction', 'desc')}#search-box")

@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit(); conn.close()
    return redirect("/#search-box")
@app.route("/add_cat", methods=["POST"])
def add_cat():
    c, p = request.form.get("new_cat", "").strip(), request.form.get("parent_cat", "").strip() or None
    if c:
        conn = sqlite3.connect(DB_FILE)
        try: 
            conn.execute("INSERT INTO categories (name, parent_name) VALUES (?, ?)", (c, p))
            conn.commit()
        except: pass
        conn.close()
    return redirect("/#search-box")

@app.route("/cleanup_orphaned_images", methods=["POST"])
def cleanup_orphaned_images():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT image_filename FROM inventory WHERE image_filename IS NOT NULL AND image_filename != ''")
    active_images = set(row[0] for row in cursor.fetchall())
    cursor.execute("SELECT DISTINCT profile_filename FROM inventory WHERE profile_filename IS NOT NULL AND profile_filename != ''")
    for row in cursor.fetchall(): active_images.add(row[0])
    conn.close()
    
    deleted_count = 0
    for path in [UPLOAD_FOLDER, PROFILES_FOLDER]:
        if os.path.exists(path):
            for filename in os.listdir(path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                    if filename not in active_images:
                        try:
                            os.remove(os.path.join(path, filename))
                            deleted_count += 1
                        except Exception: pass
    flash(f"Success! Storage cleanup complete. Purged {deleted_count} orphaned files.")
    return redirect("/#search-box")

@app.route("/export_categories_csv")
def export_categories_csv():
    output = io.StringIO(); w = csv.writer(output); w.writerow(["name", "parent_name"])
    conn = sqlite3.connect(DB_FILE)
    for r in conn.execute("SELECT name, parent_name FROM categories ORDER BY name").fetchall(): w.writerow(r)
    conn.close(); output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=categories.csv"})
@app.route("/import_categories_csv", methods=["POST"])
def import_categories_csv():
    file = request.files.get("cat_csv_file")
    if file and file.filename.endswith('.csv'):
        reader = csv.reader(io.StringIO(file.stream.read().decode("UTF-8"), newline=None))
        conn = sqlite3.connect(DB_FILE)
        conn.execute("DELETE FROM categories")
        valid_cats = set()
        for r in reader:
            if not r or "name" in r[0]: continue
            name = r[0].strip()
            parent = r[1].strip() if len(r) > 1 and r[1].strip() else None
            if name:
                valid_cats.add(name)
                try: conn.execute("INSERT INTO categories (name, parent_name) VALUES (?, ?)", (name, parent))
                except: pass
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM inventory WHERE category IS NOT NULL AND category != 'None'")
        for (item_cat,) in cur.fetchall():
            if item_cat not in valid_cats:
                conn.execute("UPDATE inventory SET category = 'None' WHERE category = ?", (item_cat,))
        conn.commit(); conn.close()
    return redirect("/#search-box")

@app.route("/export")
def export():
    output = io.StringIO(); w = csv.writer(output); w.writerow(["Location", "Part Name", "Item Type", "Quantity", "Notes", "Purchase URL", "Last Updated"])
    conn = sqlite3.connect(DB_FILE)
    for r in conn.execute("SELECT location, part_name, category, quantity, notes, purchase_url, last_updated FROM inventory ORDER BY location").fetchall(): w.writerow(r)
    conn.close(); output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=inventory.csv"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
