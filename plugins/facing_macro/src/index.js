'use strict';

import { registerRoute } from "@/routes";
import FacingMacro from './components/FacingMacro.vue';

// Register the route
registerRoute(FacingMacro, {
    Control: {
        FacingMacro: {
            icon: "mdi-arrow-collapse-down",
            caption: "Facing",
            path: "/Plugins/FacingMacro"
        }
    }
});

// Export the plugin configuration
export default {
    id: 'facing_macro',
    name: 'Facing Plugin',
    version: '1.0.0',
    author: 'Kadders',
    license: 'GPL-3.0-or-later',
    homepage: 'https://github.com/kadders/Milo-Code',
    dwcVersion: '3.5.3',
    dependencies: {}
}; 