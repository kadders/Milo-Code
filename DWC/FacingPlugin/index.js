export default class FacingPlugin {
    constructor(plugin) {
        this.plugin = plugin;
        this.name = 'Facing Operation';
        this.panels = [
            {
                component: FacingPanel,
                icon: 'mdi-plane',
                title: 'Facing Operation',
                path: '/plugins/facing'
            }
        ];
    }
}

Vue.component('facing-panel', {
    template: `
        <div>
            <v-card>
                <v-card-title>Facing Operation Settings</v-card-title>
                <v-card-text>
                    <v-container>
                        <v-alert
                            v-if="!hasWorkOffset"
                            type="warning"
                            dense
                        >
                            No work offset is set. The macro will prompt for probing before starting.
                        </v-alert>

                        <h3 class="mb-3">Roughing Parameters</h3>
                        <v-row>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="width"
                                    label="Width (X axis, mm)"
                                    type="number"
                                    required
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="depth"
                                    label="Depth (Y axis, mm)"
                                    type="number"
                                    required
                                ></v-text-field>
                            </v-col>
                        </v-row>
                        <v-row>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="cutDepth"
                                    label="Cut Depth per Pass (mm)"
                                    type="number"
                                    required
                                    hint="Default: 0.2mm"
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="passes"
                                    label="Number of Passes"
                                    type="number"
                                    required
                                ></v-text-field>
                            </v-col>
                        </v-row>
                        <v-row>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="feedRate"
                                    label="Feed Rate (mm/min)"
                                    type="number"
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="spindleSpeed"
                                    label="Spindle Speed (RPM)"
                                    type="number"
                                ></v-text-field>
                            </v-col>
                        </v-row>
                        <v-row>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="stockOffset"
                                    label="Stock Offset (mm)"
                                    type="number"
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="stepOver"
                                    label="Step Over Width (mm)"
                                    type="number"
                                ></v-text-field>
                            </v-col>
                        </v-row>
                        <v-row>
                            <v-col cols="12" md="6">
                                <v-switch
                                    v-model="coolant"
                                    label="Use Coolant"
                                ></v-switch>
                            </v-col>
                        </v-row>

                        <h3 class="mt-4 mb-3">Finishing Parameters (Optional)</h3>
                        <v-row>
                            <v-col cols="12">
                                <v-switch
                                    v-model="useFinishing"
                                    label="Enable Finishing Pass"
                                ></v-switch>
                            </v-col>
                        </v-row>
                        <v-row v-if="useFinishing">
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="finishingDoc"
                                    label="Finishing Depth of Cut (mm)"
                                    type="number"
                                    :disabled="!useFinishing"
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="finishingFeed"
                                    label="Finishing Feed Rate (mm/min)"
                                    type="number"
                                    :disabled="!useFinishing"
                                ></v-text-field>
                            </v-col>
                        </v-row>
                        <v-row v-if="useFinishing">
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="finishingSpeed"
                                    label="Finishing Spindle Speed (RPM)"
                                    type="number"
                                    :disabled="!useFinishing"
                                ></v-text-field>
                            </v-col>
                            <v-col cols="12" md="6">
                                <v-text-field
                                    v-model="finishingStepOver"
                                    label="Finishing Step Over (mm)"
                                    type="number"
                                    :placeholder="stepOver"
                                    :disabled="!useFinishing"
                                ></v-text-field>
                            </v-col>
                        </v-row>

                        <v-row class="mt-4">
                            <v-col cols="12">
                                <v-alert
                                    type="info"
                                    dense
                                >
                                    Position the probe over the front left corner of your workpiece before starting if no work offset is set.
                                </v-alert>
                            </v-col>
                        </v-row>
                    </v-container>
                </v-card-text>
                <v-card-actions>
                    <v-spacer></v-spacer>
                    <v-btn
                        color="primary"
                        @click="runFacingOperation"
                        :disabled="!isValid"
                    >
                        Run Facing Operation
                    </v-btn>
                </v-card-actions>
            </v-card>
        </div>
    `,
    data() {
        return {
            // Roughing parameters
            width: 100,
            depth: 100,
            cutDepth: 0.2,
            passes: 3,
            feedRate: 1500,
            spindleSpeed: 15000,
            stockOffset: 2,
            stepOver: 1,
            coolant: false,
            
            // Finishing parameters
            useFinishing: false,
            finishingDoc: 0.1,
            finishingFeed: 1000,
            finishingSpeed: 15000,
            finishingStepOver: null,
            hasWorkOffset: false
        }
    },
    computed: {
        isValid() {
            return this.width > 0 && 
                   this.depth > 0 && 
                   this.cutDepth > 0 && 
                   this.passes > 0 &&
                   this.stepOver > 0 &&
                   this.finishingDoc > 0;
        }
    },
    mounted() {
        // Check for work offset when component mounts
        this.checkWorkOffset();
    },
    methods: {
        async checkWorkOffset() {
            try {
                const response = await this.$store.dispatch('machine/sendCode', 'M114 S1');
                // Parse the response to check if G54 Z offset exists
                this.hasWorkOffset = response.includes('#54.Z');
            } catch (error) {
                console.warn('Failed to check work offset:', error);
                this.hasWorkOffset = false;
            }
        },
        async runFacingOperation() {
            if (!this.hasWorkOffset) {
                await this.$store.dispatch('machine/showMessage', {
                    text: 'No work offset set. The macro will prompt for probing.',
                    type: 'warning',
                    timeout: 5000
                });
            }

            let command = `M98 P"face_macro" P${this.width} Q${this.depth} R${this.cutDepth} S${this.passes} ` +
                         `F${this.feedRate} T${this.spindleSpeed} O${this.stockOffset} C${this.coolant ? 1 : 0} ` +
                         `W${this.stepOver}`;
            
            // Only add finishing parameters if finishing is enabled
            if (this.useFinishing) {
                command += ` RF${this.finishingDoc} FF${this.finishingFeed} TF${this.finishingSpeed}`;
                if (this.finishingStepOver !== null && this.finishingStepOver !== this.stepOver) {
                    command += ` WF${this.finishingStepOver}`;
                }
            }
            
            try {
                await this.$store.dispatch('machine/sendCode', command);
                this.$store.dispatch('machine/showMessage', {
                    text: 'Facing operation started',
                    type: 'success'
                });
            } catch (error) {
                this.$store.dispatch('machine/showMessage', {
                    text: 'Failed to start facing operation: ' + error.message,
                    type: 'error'
                });
            }
        }
    }
}); 