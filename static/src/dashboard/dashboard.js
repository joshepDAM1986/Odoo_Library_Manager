/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
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
        this.state = useState({ sections: [], canCreateLoan: false, canCreateBook: false });
        onWillStart(() => this.loadStats());
    }

    // Definicion de las tarjetas: que contar y con que filtro
    getSections() {
        const today = todayString();
        return [
            {
                title: _t("Books"),
                icon: "fa-book",
                cards: [
                    { label: _t("Total books"), model: "library.book", domain: [], color: "primary", icon: "fa-book" },
                    { label: _t("Available"), model: "library.book", domain: [["state", "=", "available"]], color: "success", icon: "fa-check-circle" },
                    { label: _t("Borrowed"), model: "library.book", domain: [["state", "=", "borrowed"]], color: "warning", icon: "fa-hand-paper-o" },
                    { label: _t("Lost"), model: "library.book", domain: [["state", "=", "lost"]], color: "danger", icon: "fa-question-circle" },
                ],
            },
            {
                title: _t("Members"),
                icon: "fa-users",
                cards: [
                    { label: _t("Active members"), model: "library.member", domain: [["state", "=", "active"]], color: "success", icon: "fa-user" },
                    { label: _t("Suspended"), model: "library.member", domain: [["state", "=", "suspended"]], color: "danger", icon: "fa-ban" },
                ],
            },
            {
                title: _t("Loans"),
                icon: "fa-exchange",
                cards: [
                    { label: _t("Ongoing"), model: "library.loan", domain: [["state", "=", "ongoing"]], color: "primary", icon: "fa-exchange" },
                    { label: _t("Overdue"), model: "library.loan", domain: [["state", "=", "ongoing"], ["due_date", "<", today]], color: "danger", icon: "fa-clock-o" },
                    { label: _t("Returned"), model: "library.loan", domain: [["state", "=", "returned"]], color: "secondary", icon: "fa-undo" },
                ],
            },
        ];
    }

    async loadStats() {
        const sections = this.getSections();
        const cards = sections.flatMap((section) => section.cards);
        // Todas las consultas en paralelo (incluye los permisos de creación,
        // para no enseñar botones que darían error a un lector)
        const [counts, canCreateLoan, canCreateBook] = await Promise.all([
            Promise.all(
                cards.map((card) => this.orm.searchCount(card.model, card.domain))
            ),
            this.orm.call("library.loan", "check_access_rights", ["create", false]),
            this.orm.call("library.book", "check_access_rights", ["create", false]),
        ]);
        cards.forEach((card, index) => {
            card.count = counts[index];
        });
        this.state.sections = sections;
        this.state.canCreateLoan = canCreateLoan;
        this.state.canCreateBook = canCreateBook;
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

    newLoan() {
        this.newRecord("library.loan", _t("New Loan"));
    }

    newBook() {
        this.newRecord("library.book", _t("New Book"));
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
