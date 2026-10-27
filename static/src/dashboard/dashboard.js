/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

// Fecha de hoy en formato YYYY-MM-DD (hora local del navegador)
function todayString() {
    const d = new Date();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${d.getFullYear()}-${month}-${day}`;
}

export class LibraryDashboard extends Component {
    static template = "library_manager.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ sections: [] });
        onWillStart(() => this.loadStats());
    }

    // Definicion de las tarjetas: que contar y con que filtro
    getSections() {
        const today = todayString();
        return [
            {
                title: "Books",
                cards: [
                    { label: "Total books", model: "library.book", domain: [], color: "primary" },
                    { label: "Available", model: "library.book", domain: [["state", "=", "available"]], color: "success" },
                    { label: "Borrowed", model: "library.book", domain: [["state", "=", "borrowed"]], color: "warning" },
                    { label: "Lost", model: "library.book", domain: [["state", "=", "lost"]], color: "danger" },
                ],
            },
            {
                title: "Members",
                cards: [
                    { label: "Active members", model: "library.member", domain: [["state", "=", "active"]], color: "success" },
                    { label: "Suspended", model: "library.member", domain: [["state", "=", "suspended"]], color: "danger" },
                ],
            },
            {
                title: "Loans",
                cards: [
                    { label: "Ongoing", model: "library.loan", domain: [["state", "=", "ongoing"]], color: "primary" },
                    { label: "Overdue", model: "library.loan", domain: [["state", "=", "ongoing"], ["due_date", "<", today]], color: "danger" },
                    { label: "Returned", model: "library.loan", domain: [["state", "=", "returned"]], color: "secondary" },
                ],
            },
        ];
    }

    async loadStats() {
        const sections = this.getSections();
        const cards = sections.flatMap((section) => section.cards);
        // Todas las consultas en paralelo
        const counts = await Promise.all(
            cards.map((card) => this.orm.searchCount(card.model, card.domain))
        );
        cards.forEach((card, index) => {
            card.count = counts[index];
        });
        this.state.sections = sections;
    }

    // Abre la lista del modelo con el mismo filtro de la tarjeta
    openCard(card) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: card.label,
            res_model: card.model,
            views: [[false, "list"], [false, "form"]],
            domain: card.domain,
        });
    }

    // Abre un formulario vacio para crear un registro nuevo
    newRecord(model, name) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: name,
            res_model: model,
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("library_manager.dashboard", LibraryDashboard);
