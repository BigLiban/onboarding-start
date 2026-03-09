/*
 * Copyright (c) 2024 Mohamed Bekdach
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module spi_peripheral (
    input  wire       clk,      // clock
    input  wire       rst_n,     // reset_n - low to reset
    input  wire       nCS_input,
    input  wire       COPI_input,
    input  wire       SCLK_input,
    output  reg [7:0] en_reg_out_7_0,
    output  reg [7:0] en_reg_out_15_8,
    output  reg [7:0] en_reg_pwm_7_0,
    output  reg [7:0] en_reg_pwm_15_8,
    output  reg [7:0] pwm_duty_cycle
);

parameter WRITE = 1;

reg [2:0] cdc_reg_1, cdc_reg_2;
wire nCS, COPI, SCLK;
assign {nCS, COPI, SCLK} = cdc_reg_2;

// logic for doing a transaction
reg [15:0] dataBuffer;
reg [3:0] transaction_counter;
reg old_nCS, old_SCLK;
wire nCS_posedge = ~old_nCS & nCS;
wire SCLK_posedge = ~old_SCLK & SCLK;
wire transaction_complete = nCS_posedge && transaction_counter == 4'd15;

always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
        dataBuffer <= 16'b0;
        transaction_counter <= 4'b0;
        old_nCS             <= 1'b1;  // active-low nCS
        old_SCLK            <= 1'b0;
        cdc_reg_1           <= 3'b0;
        cdc_reg_2           <= 3'b0;
    end else begin 
        // CDC on inputs
        cdc_reg_1 <= {nCS_input, COPI_input, SCLK_input};
        cdc_reg_2 <= cdc_reg_1;

        // nCS posedge detector
        old_nCS <= nCS;
        // SCLK posedge detector
        old_SCLK <= SCLK;

        if(~nCS) begin
            if (SCLK_posedge) begin
                transaction_counter <= transaction_counter + 1;
                dataBuffer <= {dataBuffer[14:0], COPI}; // wire the older 15 bits + the new bit
            end
        end else begin
            if (transaction_complete) begin
                // clear data buffer for next incoming transaction
                dataBuffer <= 16'b0;
            end
        end
    end   

end

wire rw_bit = dataBuffer[15];
wire [6:0] address_bits = dataBuffer[14:8];
wire [7:0] data_bits = dataBuffer[7:0];
// logic for processing transaction
always @(posedge clk or negedge rst_n) begin
    if(~rst_n) begin
        en_reg_out_7_0  <= 8'b0;
        en_reg_out_15_8 <= 8'b0;
        en_reg_pwm_7_0  <= 8'b0;
        en_reg_pwm_15_8 <= 8'b0;
        pwm_duty_cycle  <= 8'b0;
    end else if (~transaction_complete) begin
        // reads are ignored
        if(rw_bit == WRITE) begin
            case (address_bits)
                7'h00 : en_reg_out_7_0  <= data_bits;
                7'h01 : en_reg_out_15_8 <= data_bits;
                7'h02 : en_reg_pwm_7_0  <= data_bits;
                7'h03 : en_reg_pwm_15_8 <= data_bits;
                7'h04 : pwm_duty_cycle  <= data_bits;
                default: ; // ignore invalid addresses
            endcase
        end
    end
end

endmodule