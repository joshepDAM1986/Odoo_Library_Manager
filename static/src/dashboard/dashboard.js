/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, useState } from "@odoo/owl";

// Modelos cuya acción de menú tiene vista kanban (kanban,tree,form)
const KANBAN_MODELS = ["library.book", "library.author", "library.member"];

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
        this.state = useState({
            sections: [],
            canCreateLoan: false,
            canCreateBook: false,
            heroTitle: _t("Your library, in good company."),
            heroSubtitle: _t("A thoughtful overview of books, readers and loans."),
            heroKicker: _t("A library in motion"),
            heroMessage: _t("Good stories always find their next reader."),
            heroDetail: _t("Your collection, members and everyday activity — at a glance."),
        });
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
                    { label: _t("Total books"), model: "library.book", domain: [], total: true, color: "primary", icon: "fa-book" },
                    { label: _t("Available"), model: "library.book", domain: [["state", "=", "available"]], state: "available", color: "success", icon: "fa-check-circle" },
                    { label: _t("Borrowed"), model: "library.book", domain: [["state", "=", "borrowed"]], state: "borrowed", color: "warning", icon: "fa-hand-paper-o" },
                    { label: _t("Lost"), model: "library.book", domain: [["state", "=", "lost"]], state: "lost", color: "danger", icon: "fa-question-circle" },
                ],
            },
            {
                title: _t("Members"),
                icon: "fa-users",
                cards: [
                    { label: _t("Active members"), model: "library.member", domain: [["state", "=", "active"]], state: "active", color: "success", icon: "fa-user" },
                    { label: _t("Suspended"), model: "library.member", domain: [["state", "=", "suspended"]], state: "suspended", color: "danger", icon: "fa-ban" },
                ],
            },
            {
                title: _t("Loans"),
                icon: "fa-exchange",
                cards: [
                    { label: _t("Ongoing"), model: "library.loan", domain: [["state", "=", "ongoing"]], state: "ongoing", color: "primary", icon: "fa-exchange" },
                    { label: _t("Overdue"), model: "library.loan", domain: [["state", "=", "ongoing"], ["due_date", "<", today]], color: "danger", icon: "fa-clock-o" },
                    { label: _t("Returned"), model: "library.loan", domain: [["state", "=", "returned"]], state: "returned", color: "secondary", icon: "fa-undo" },
                ],
            },
        ];
    }

    // Cuenta los registros de un modelo agrupados por estado con UNA sola
    // consulta (en lugar de un searchCount por tarjeta).
    async countByState(model) {
        const groups = await this.orm.readGroup(model, [], ["state"], ["state"]);
        const byState = {};
        let total = 0;
        for (const group of groups) {
            const count = group.__count ?? group.state_count ?? 0;
            byState[group.state] = (byState[group.state] || 0) + count;
            total += count;
        }
        return { byState, total };
    }

    async loadStats() {
        const sections = this.getSections();
        const cards = sections.flatMap((section) => section.cards);
        // Las tarjetas con "state" o "total" salen de un único agrupado por
        // modelo; el resto (p. ej. "Overdue", que depende de la fecha) se cuenta
        // con su propio dominio.
        const groupedModels = [
            ...new Set(cards.filter((card) => card.state || card.total).map((card) => card.model)),
        ];
        const singleCards = cards.filter((card) => !card.state && !card.total);
        // Todas las consultas en paralelo (incluye los permisos de creación,
        // para no enseñar botones que darían error a un lector)
        const [grouped, singleCounts, canCreateLoan, canCreateBook] = await Promise.all([
            Promise.all(groupedModels.map((model) => this.countByState(model))),
            Promise.all(
                singleCards.map((card) => this.orm.searchCount(card.model, card.domain))
            ),
            this.orm.call("library.loan", "check_access_rights", ["create", false]),
            this.orm.call("library.book", "check_access_rights", ["create", false]),
        ]);
        const countsByModel = Object.fromEntries(
            groupedModels.map((model, index) => [model, grouped[index]])
        );
        cards.forEach((card) => {
            if (card.total) {
                card.count = countsByModel[card.model].total;
            } else if (card.state) {
                card.count = countsByModel[card.model].byState[card.state] || 0;
            }
        });
        singleCards.forEach((card, index) => {
            card.count = singleCounts[index];
        });
        this.state.sections = sections;
        this.state.canCreateLoan = canCreateLoan;
        this.state.canCreateBook = canCreateBook;
    }

    // Abre la lista del modelo con el mismo filtro de la tarjeta
    openCard(card) {
        // Mismas vistas que las acciones del menú: sin kanban la lista sería
        // la única vista y no aparecerían los botones para cambiar de vista.
        const views = KANBAN_MODELS.includes(card.model)
            ? [[false, "kanban"], [false, "list"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: card.label,
            res_model: card.model,
            views,
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