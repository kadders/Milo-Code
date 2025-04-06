<template>
  <v-container>
    <v-form @submit.prevent="handleSubmit">
      <v-card class="mb-4">
        <v-card-title>Required Parameters</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.width"
                label="Width (X axis) (mm)"
                type="number"
                required
                :rules="[v => v > 0 || 'Width must be greater than 0']"
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.depth"
                label="Depth (Y axis) (mm)"
                type="number"
                required
                :rules="[v => v > 0 || 'Depth must be greater than 0']"
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.numPasses"
                label="Number of Passes"
                type="number"
                required
                :rules="[v => v > 0 || 'Number of passes must be greater than 0']"
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.toolDiameter"
                label="Tool Diameter (mm)"
                type="number"
                required
                :rules="[v => v > 0 || 'Tool diameter must be greater than 0']"
              ></v-text-field>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-title>Optional Parameters</v-card-title>
        <v-card-text>
          <v-row>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.cutDepth"
                label="Depth of Cut (mm)"
                type="number"
                step="0.1"
                hint="Default: 0.2"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.feedRate"
                label="Feed Rate (mm/min)"
                type="number"
                hint="Default: 1500"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.spindleSpeed"
                label="Spindle Speed (RPM)"
                type="number"
                hint="Default: 15000"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.stockOffset"
                label="Stock Offset (mm)"
                type="number"
                hint="Default: 2"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-switch
                v-model="formData.useCoolant"
                label="Use Coolant"
              ></v-switch>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.stepOver"
                label="Step Over (mm)"
                type="number"
                hint="Default: 1"
                persistent-hint
              ></v-text-field>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-title>
          Finishing Pass
          <v-switch
            v-model="formData.doFinishing"
            label="Enable Finishing Pass"
            class="ml-4"
          ></v-switch>
        </v-card-title>
        <v-card-text v-if="formData.doFinishing">
          <v-row>
            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.finishDoc"
                label="Finishing Depth of Cut (mm)"
                type="number"
                step="0.1"
                hint="Default: 0.1"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.finishFeed"
                label="Finishing Feed Rate (mm/min)"
                type="number"
                hint="Default: 1000"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.finishSpeed"
                label="Finishing Spindle Speed (RPM)"
                type="number"
                hint="Default: 15000"
                persistent-hint
              ></v-text-field>
            </v-col>

            <v-col cols="12" md="4">
              <v-text-field
                v-model="formData.finishStep"
                label="Finishing Step Over (mm)"
                type="number"
                hint="Default: Same as regular step over"
                persistent-hint
              ></v-text-field>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-title>Start Position</v-card-title>
        <v-card-text>
          <v-radio-group v-model="formData.startFromCenter" row>
            <v-radio label="Corner" :value="false"></v-radio>
            <v-radio label="Center" :value="true"></v-radio>
          </v-radio-group>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-title>Z Reference</v-card-title>
        <v-card-text>
          <v-radio-group v-model="formData.zReference" row>
            <v-radio label="Probe Surface" :value="'probe'"></v-radio>
            <v-radio label="Manual Input" :value="'manual'"></v-radio>
          </v-radio-group>

          <v-text-field
            v-if="formData.zReference === 'manual'"
            v-model="formData.zHeight"
            label="Z Reference Height (mm)"
            type="number"
            class="mt-4"
          ></v-text-field>
        </v-card-text>
      </v-card>

      <v-card class="mb-4">
        <v-card-title>Tool Offset</v-card-title>
        <v-card-text>
          <v-switch
            v-model="formData.checkToolOffset"
            label="Check Tool Offset Before Operation"
          ></v-switch>
          
          <v-alert
            v-if="formData.checkToolOffset"
            type="info"
            class="mt-4"
          >
            This will run G37 to check and update the tool offset before starting the facing operation.
            Make sure the tool is properly mounted and the toolsetter is configured.
          </v-alert>
        </v-card-text>
      </v-card>

      <v-alert
        v-if="error"
        type="error"
        dismissible
      >
        {{ error }}
      </v-alert>
      
      <v-alert
        v-if="success"
        type="success"
        dismissible
      >
        Command sent successfully!
      </v-alert>

      <v-btn
        color="primary"
        type="submit"
        :disabled="!isValid"
      >
        Run Facing Operation
      </v-btn>
    </v-form>
  </v-container>
</template>

<script>
export default {
  name: 'FacingMacro',
  metaInfo: {
    title: 'Facing Macro',
    icon: 'mdi-cutter',
    caption: 'Facing Macro',
    path: '/Plugins/FacingMacro'
  },
  data() {
    return {
      formData: {
        width: '',
        depth: '',
        numPasses: '',
        toolDiameter: '',
        cutDepth: '0.2',
        feedRate: '1500',
        spindleSpeed: '15000',
        stockOffset: '2',
        useCoolant: false,
        stepOver: '1',
        doFinishing: false,
        finishDoc: '0.1',
        finishFeed: '1000',
        finishSpeed: '15000',
        finishStep: '',
        startFromCenter: false,
        zReference: 'probe',
        zHeight: '',
        checkToolOffset: true
      },
      error: null,
      success: false
    }
  },
  computed: {
    isValid() {
      return this.formData.width > 0 && 
             this.formData.depth > 0 && 
             this.formData.numPasses > 0 &&
             this.formData.toolDiameter > 0 &&
             (this.formData.zReference === 'probe' || (this.formData.zReference === 'manual' && this.formData.zHeight !== ''));
    }
  },
  methods: {
    async handleSubmit() {
      this.error = null;
      this.success = false;
      
      try {
        // Format parameters to ensure proper decimal values
        const width = parseFloat(this.formData.width).toFixed(2);
        const depth = parseFloat(this.formData.depth).toFixed(2);
        const numPasses = parseInt(this.formData.numPasses);
        const toolDiameter = parseFloat(this.formData.toolDiameter).toFixed(2);
        const zParam = this.formData.startFromCenter ? '1' : '0';
        
        let command = 'M98 P"0:/macros/Facing/facing_macro.gcode"';
        command += ` W${width} D${depth} N${numPasses} E${toolDiameter} Z${zParam}`;
        
        // Add optional parameters if they differ from defaults
        if (this.formData.cutDepth !== '0.2') {
          command += ` H${parseFloat(this.formData.cutDepth).toFixed(2)}`;
        }
        
        if (this.formData.feedRate !== '1500') {
          command += ` F${parseInt(this.formData.feedRate)}`;
        }
        
        if (this.formData.spindleSpeed !== '15000') {
          command += ` S${parseInt(this.formData.spindleSpeed)}`;
        }
        
        if (this.formData.stockOffset !== '2') {
          command += ` O${parseInt(this.formData.stockOffset)}`;
        }
        
        if (this.formData.useCoolant) {
          command += ' C1';
        }
        
        if (this.formData.stepOver !== '1') {
          command += ` T${parseInt(this.formData.stepOver)}`;
        }
        
        // Add finishing parameters if enabled
        if (this.formData.doFinishing) {
          if (this.formData.finishDoc !== '0.1') command += ` I${parseFloat(this.formData.finishDoc).toFixed(2)}`;
          if (this.formData.finishFeed !== '1000') command += ` J${parseInt(this.formData.finishFeed)}`;
          if (this.formData.finishSpeed !== '15000') command += ` K${parseInt(this.formData.finishSpeed)}`;
          if (this.formData.finishStep) command += ` L${parseFloat(this.formData.finishStep).toFixed(2)}`;
        }

        // Add Z reference parameter
        if (this.formData.zReference === 'manual') {
          command += ` ZH${this.formData.zHeight}`;
        }

        await this.$store.dispatch('machine/sendCode', command);
        this.$store.dispatch('machine/showMessage', 'Facing operation started', 'success');
        this.success = true;
      } catch (error) {
        this.error = error.message || 'Failed to send command';
        console.error('Error sending command:', error);
      }
    }
  }
}
</script>

<style scoped>
.v-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
</style>