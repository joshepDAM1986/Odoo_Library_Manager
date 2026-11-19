/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

const fieldRegistry = registry.category("fields");

export class LibraryNaField extends Component {
    static template = "library_manager.NaField";
    static props = ["*"];
    static baseName = null;

    get baseField() {
        return fieldRegistry.get(this.constructor.baseName);
    }

    get isEmpty() {
        return !this.props.record.data[this.props.name];
    }
}

export class LibraryNaChar extends LibraryNaField {
    static baseName = "char";
}

export class LibraryNaInteger extends LibraryNaField {
    static baseName = "integer";
}

export class LibraryNaText extends LibraryNaField {
    static baseName = "text";
}

export class LibraryNaDate extends LibraryNaField {
    static baseName = "date";
}

function naFieldDefinition(component, baseName, supportedTypes, displayName) {
    return {
        component,
        displayName,
        supportedTypes,
        extractProps: (...args) => {
            const base = fieldRegistry.get(baseName);
            return base.extractProps ? base.extractProps(...args) : {};
        },
        get additionalClasses() {
            const baseClasses = fieldRegistry.get(baseName).additionalClasses || [];
            return [`o_field_${baseName}`, ...baseClasses];
        },
    };
}

fieldRegistry.add(
    "library_na_char",
    naFieldDefinition(LibraryNaChar, "char", ["char"], "Text (NA if empty)")
);
fieldRegistry.add(
    "library_na_integer",
    naFieldDefinition(LibraryNaInteger, "integer", ["integer"], "Integer (NA if 0)")
);
fieldRegistry.add(
    "library_na_text",
    naFieldDefinition(LibraryNaText, "text", ["text"], "Multiline text (NA if empty)")
);
fieldRegistry.add(
    "library_na_date",
    naFieldDefinition(LibraryNaDate, "date", ["date"], "Date (NA if empty)")
);