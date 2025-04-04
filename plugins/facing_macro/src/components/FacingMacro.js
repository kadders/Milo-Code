import React, { useState } from 'react';
import { Button, Form, FormGroup, Label, Input, Card, CardBody, CardHeader } from 'reactstrap';

const FacingMacro = () => {
    const [formData, setFormData] = useState({
        width: '',
        depth: '',
        numPasses: '',
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
        finishStep: '1'
    });

    const handleInputChange = (e) => {
        const { name, value, type, checked } = e.target;
        setFormData(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        
        // Construct the M98 command with parameters
        let command = 'M98 P"face_macro"';
        
        // Add parameters based on form data
        if (formData.width) command += ` P${formData.width}`;
        if (formData.depth) command += ` Q${formData.depth}`;
        if (formData.cutDepth) command += ` R${formData.cutDepth}`;
        if (formData.numPasses) command += ` S${formData.numPasses}`;
        if (formData.feedRate) command += ` F${formData.feedRate}`;
        if (formData.spindleSpeed) command += ` T${formData.spindleSpeed}`;
        if (formData.stockOffset) command += ` O${formData.stockOffset}`;
        if (formData.useCoolant) command += ' C1';
        if (formData.stepOver) command += ` W${formData.stepOver}`;
        
        if (formData.doFinishing) {
            if (formData.finishDoc) command += ` RF${formData.finishDoc}`;
            if (formData.finishFeed) command += ` FF${formData.finishFeed}`;
            if (formData.finishSpeed) command += ` TF${formData.finishSpeed}`;
            if (formData.finishStep) command += ` WF${formData.finishStep}`;
        }

        // Send command to DWC
        try {
            await fetch('/machine/code', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    code: command
                })
            });
        } catch (error) {
            console.error('Error sending command:', error);
        }
    };

    return (
        <Card>
            <CardHeader>Facing Macro</CardHeader>
            <CardBody>
                <Form onSubmit={handleSubmit}>
                    <FormGroup>
                        <Label for="width">Width (mm)</Label>
                        <Input
                            type="number"
                            name="width"
                            id="width"
                            value={formData.width}
                            onChange={handleInputChange}
                            required
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="depth">Depth (mm)</Label>
                        <Input
                            type="number"
                            name="depth"
                            id="depth"
                            value={formData.depth}
                            onChange={handleInputChange}
                            required
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="numPasses">Number of Passes</Label>
                        <Input
                            type="number"
                            name="numPasses"
                            id="numPasses"
                            value={formData.numPasses}
                            onChange={handleInputChange}
                            required
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="cutDepth">Depth of Cut (mm)</Label>
                        <Input
                            type="number"
                            name="cutDepth"
                            id="cutDepth"
                            value={formData.cutDepth}
                            onChange={handleInputChange}
                            step="0.1"
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="feedRate">Feed Rate (mm/min)</Label>
                        <Input
                            type="number"
                            name="feedRate"
                            id="feedRate"
                            value={formData.feedRate}
                            onChange={handleInputChange}
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="spindleSpeed">Spindle Speed (RPM)</Label>
                        <Input
                            type="number"
                            name="spindleSpeed"
                            id="spindleSpeed"
                            value={formData.spindleSpeed}
                            onChange={handleInputChange}
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="stockOffset">Stock Offset (mm)</Label>
                        <Input
                            type="number"
                            name="stockOffset"
                            id="stockOffset"
                            value={formData.stockOffset}
                            onChange={handleInputChange}
                        />
                    </FormGroup>

                    <FormGroup>
                        <Label for="stepOver">Step Over (mm)</Label>
                        <Input
                            type="number"
                            name="stepOver"
                            id="stepOver"
                            value={formData.stepOver}
                            onChange={handleInputChange}
                        />
                    </FormGroup>

                    <FormGroup check>
                        <Label check>
                            <Input
                                type="checkbox"
                                name="useCoolant"
                                checked={formData.useCoolant}
                                onChange={handleInputChange}
                            />
                            Enable Coolant
                        </Label>
                    </FormGroup>

                    <FormGroup check>
                        <Label check>
                            <Input
                                type="checkbox"
                                name="doFinishing"
                                checked={formData.doFinishing}
                                onChange={handleInputChange}
                            />
                            Add Finishing Pass
                        </Label>
                    </FormGroup>

                    {formData.doFinishing && (
                        <>
                            <FormGroup>
                                <Label for="finishDoc">Finishing Depth of Cut (mm)</Label>
                                <Input
                                    type="number"
                                    name="finishDoc"
                                    id="finishDoc"
                                    value={formData.finishDoc}
                                    onChange={handleInputChange}
                                    step="0.1"
                                />
                            </FormGroup>

                            <FormGroup>
                                <Label for="finishFeed">Finishing Feed Rate (mm/min)</Label>
                                <Input
                                    type="number"
                                    name="finishFeed"
                                    id="finishFeed"
                                    value={formData.finishFeed}
                                    onChange={handleInputChange}
                                />
                            </FormGroup>

                            <FormGroup>
                                <Label for="finishSpeed">Finishing Spindle Speed (RPM)</Label>
                                <Input
                                    type="number"
                                    name="finishSpeed"
                                    id="finishSpeed"
                                    value={formData.finishSpeed}
                                    onChange={handleInputChange}
                                />
                            </FormGroup>

                            <FormGroup>
                                <Label for="finishStep">Finishing Step Over (mm)</Label>
                                <Input
                                    type="number"
                                    name="finishStep"
                                    id="finishStep"
                                    value={formData.finishStep}
                                    onChange={handleInputChange}
                                />
                            </FormGroup>
                        </>
                    )}

                    <Button color="primary" type="submit">Run Facing Operation</Button>
                </Form>
            </CardBody>
        </Card>
    );
};

export default FacingMacro; 