/* ==========================================================================
   MINA — TASK CARD RENDERER (Hybrid Edition: H3 + R3 + T2)
   ==========================================================================
   Responsibilities:
   - Create the DOM for a task card
   - Update ALL user-visible fields: title, status, priority, labels,
     description, due date, assignee, transcript flags
   - Dynamically create DOM nodes if missing
   - Maintain compatibility with existing markup
   - Ensure stable DOM structure for the UI Orchestrator
   - Add wrapper for Tier 3 (labels + description) IF missing

   NOT RESPONSIBLE FOR:
   - Moving cards between Active/Archived (handled by orchestrator)
   - High-level hydration or sorting
   - State syncing (handled by Optimistic UI + TaskStateStore)
   ========================================================================== */


/* ==========================================================================
   SAFE QUERY HELPERS
   --------------------------------------------------------------------------
   These ensure the renderer never crashes even if card structure changes.
   ========================================================================== */

const TaskCardRenderer = {

    /* Utility: find a child element */
    _qs(parent, selector) {
        return parent ? parent.querySelector(selector) : null;
    },

    /* Utility: create element with class */
    _make(tag, className) {
        const el = document.createElement(tag);
        if (className) el.className = className;
        return el;
    },

    /* Utility: clear children */
    _clear(el) {
        if (el) el.innerHTML = "";
    },



    /* ==========================================================================
       CREATE CARD
       ========================================================================== */
    createCard(task) {

        /* ===== MINA_FIX_START: CARD CREATION ===== */

        const card = document.createElement("div");
        card.className = "task-card";
        card.dataset.taskId = task.id;
        card.dataset.status = task.status;
        if (task.status === "completed") card.classList.add("completed");

        /* --- TIER 1: Header row --- */
        const header = this._make("div", "task-card-header");

        // Checkbox / Status toggle
        const checkbox = this._make("div", "task-checkbox");
        checkbox.dataset.action = "toggle-status";
        checkbox.innerHTML = `
            <span class="checkbox-icon ${task.status === "completed" ? "checked" : ""}"></span>
        `;
        header.appendChild(checkbox);

        // Title
        const titleEl = this._make("h3", "task-title");
        titleEl.textContent = task.title || "(Untitled)";
        header.appendChild(titleEl);

        // Priority
        const priorityDot = this._make("span", `priority-dot priority-${task.priority || "none"}`);
        header.appendChild(priorityDot);

        // Pin toggle
        const pin = this._make("span", "task-pin");
        pin.dataset.action = "toggle-pin";
        pin.textContent = task.is_pinned ? "📌" : "📍";
        header.appendChild(pin);

        card.appendChild(header);



        /* --- TIER 2: Meta row (due date, assignee, transcript flag) --- */
        const meta = this._make("div", "task-meta-row");

        // Due Date
        const dueDateEl = this._make("span", "due-date-compact");
        if (task.due_date) {
            dueDateEl.textContent = task.due_date;
            // Example: add overdue / due-soon classes
            const due = new Date(task.ddue_date);
            const now = new Date();
            if (due < now) dueDateEl.classList.add("overdue");
        } else {
            dueDateEl.textContent = "";
        }
        meta.appendChild(dueDateEl);

        // Assignee
        const assigneeEl = this._make("span", "assignee-compact");
        assigneeEl.textContent = task.assignee || "";
        meta.appendChild(assigneeEl);

        // Transcript / AI Indicator
        const aiEl = this._make("span", "transcript-indicator");
        if (task.transcript_flag) {
            aiEl.textContent = "🧠 From meeting";
        } else {
            aiEl.style.display = "none";
        }
        meta.appendChild(aiEl);

        card.appendChild(meta);



        /* --- TIER 3: Labels + Description wrapper (conditionally created) --- */
        let tier3 = this._qs(card, ".task-card__details");
        if (!tier3) {
            tier3 = this._make("div", "task-card__details");
            card.appendChild(tier3);
        }

        // Labels
        const labelsWrapper = this._make("div", "labels-compact");
        if (Array.isArray(task.labels)) {
            task.labels.forEach(lbl => {
                const lblEl = this._make("span", "label-compact");
                lblEl.textContent = lbl;
                labelsWrapper.appendChild(lblEl);
            });
        }
        tier3.appendChild(labelsWrapper);

        // Description (only if exists)
        if (task.description) {
            const descWrap = this._make("div", "task-description-preview");
            const descText = this._make("p", "description-text");
            descText.textContent = task.description;
            descWrap.appendChild(descText);
            tier3.appendChild(descWrap);
        }

        return card;

        /* ===== MINA_FIX_END ===== */
    },



    /* ==========================================================================
       UPDATE CARD
       ========================================================================== */
    updateCard(card, task) {

        if (!card) return;

        /* ===== MINA_FIX_START: TITLE ===== */
        const title = this._qs(card, ".task-title");
        if (title) title.textContent = task.title || "(Untitled)";
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: STATUS / CHECKBOX ===== */
        card.dataset.status = task.status;
        if (task.status === "completed") {
            card.classList.add("completed");
        } else {
            card.classList.remove("completed");
        }

        const checkbox = this._qs(card, ".checkbox-icon");
        if (checkbox) {
            if (task.status === "completed") checkbox.classList.add("checked");
            else checkbox.classList.remove("checked");
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: PRIORITY ===== */
        const priorityDot = this._qs(card, ".priority-dot");
        if (priorityDot) {
            priorityDot.className = `priority-dot priority-${task.priority || "none"}`;
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: PIN ===== */
        const pin = this._qs(card, ".task-pin");
        if (pin) {
            pin.textContent = task.is_pinned ? "📌" : "📍";
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: DUE DATE ===== */
        const due = this._qs(card, ".due-date-compact");
        if (due) {
            if (task.due_date) {
                due.textContent = task.due_date;
                due.classList.remove("overdue", "due-soon");
                // add logic here if needed based on date proximity
            } else {
                due.textContent = "";
                due.classList.remove("overdue", "due-soon");
            }
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: ASSIGNEE ===== */
        const assignee = this._qs(card, ".assignee-compact");
        if (assignee) {
            assignee.textContent = task.assignee || "";
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: LABELS ===== */
        const tier3 = this._qs(card, ".task-card__details") ||
                      card.appendChild(this._make("div", "task-card__details"));

        let labelsWrap = this._qs(tier3, ".labels-compact");
        if (!labelsWrap) {
            labelsWrap = this._make("div", "labels-compact");
            tier3.prepend(labelsWrap);
        }
        this._clear(labelsWrap);

        if (Array.isArray(task.labels)) {
            task.labels.forEach(lbl => {
                const lblEl = this._make("span", "label-compact");
                lblEl.textContent = lbl;
                labelsWrap.appendChild(lblEl);
            });
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: DESCRIPTION ===== */
        let descWrap = this._qs(tier3, ".task-description-preview");

        if (task.description) {
            if (!descWrap) {
                descWrap = this._make("div", "task-description-preview");
                const descText = this._make("p", "description-text");
                descText.textContent = task.description;
                descWrap.appendChild(descText);
                tier3.appendChild(descWrap);
            } else {
                const descText = this._qs(descWrap, ".description-text") ||
                                 descWrap.appendChild(this._make("p", "description-text"));
                descText.textContent = task.description;
            }
        } else {
            if (descWrap) descWrap.remove();
        }
        /* ===== MINA_FIX_END ===== */


        /* ===== MINA_FIX_START: TRANSCRIPT FLAG ===== */
        const ai = this._qs(card, ".transcript-indicator");
        if (ai) {
            if (task.transcript_flag) {
                ai.style.display = "";
                ai.textContent = "🧠 From meeting";
            } else {
                ai.style.display = "none";
            }
        }
        /* ===== MINA_FIX_END ===== */
    }

};