/*
 * Copyright (c) 2024 Mohamed Bekdach
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_uwasic_onboarding_mohamed_bekdach (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
  
  // Create wires to refer to the values of the registers
  wire [7:0] en_reg_out_7_0;
  wire [7:0] en_reg_out_15_8;
  wire [7:0] en_reg_pwm_7_0;
  wire [7:0] en_reg_pwm_15_8;
  wire [7:0] pwm_duty_cycle;

  // Instantiate the PWM module
  pwm_peripheral pwm_peripheral_inst (
    .clk(clk),
    .rst_n(rst_n),
    .en_reg_out_7_0(en_reg_out_7_0),
    .en_reg_out_15_8(en_reg_out_15_8),
    .en_reg_pwm_7_0(en_reg_pwm_7_0),
    .en_reg_pwm_15_8(en_reg_pwm_15_8),		
    .pwm_duty_cycle(pwm_duty_cycle),
    .out({uio_out, uo_out})
  );
);

  parameter READ = 0,
  WRITE = 1,
  MAX_ADDRESS = 4;

  reg [2:0] cdc_reg_1, cdc_reg_2;

  // CDC on inputs
  always @(posedge clk or negedge rst_n) begin
    if (~rst_n) begin
      cdc_reg_1 <= 3'b0;
      cdc_reg_2 <= 3'b0;
    end else begin
      cdc_reg_1 <= ui_in[2:0];
      cdc_reg_2 <= cdc_reg_1;
    end
  end

  wire COPI, nCS, SCLK;
  assign {nCS, COPI, SCLK} = cdc_reg_2;

  // logic for doing a transaction
  reg [15:0] dataBuffer;
  reg [4:0] transaction_counter
  reg old_nCS, nCS_posedge, transaction_complete;

  always @(posedge clk or negedge rst_n) begin
    // nCS posedge detector
    old_nCS <= nCS;
    nCS_posedge <= ~old_nCS & nCS;

    if (~rst_n) begin
      dataBuffer <= 16'b0;
      transaction_counter <= 5'b1;
      transaction_complete <= 1'b0;
    end else if(~nCS) begin
      transaction_complete <= 1'b0;
      transaction_counter <= transaction_counter + 1;
      if(transaction_counter == 5'b1) begin
        dataBuffer <= dataBuffer | {15'b0, COPI};
      end else if (transaction_counter == 5'd16) begin
        transaction_counter <= 5'b1;
      end else begin
        dataBuffer <= (dataBuffer << 1) | {15'b0, COPI};
      end
    end else begin
      if (nCS_posedge) begin
        // transaction has been completed
        transaction_complete <= 1'b1;
      end else if (transaction_processed) begin
        transaction_complete <= 1'b0;
        // clear data buffer for next incoming transaction
        dataBuffer <= 16'b0;
      end
    end
    
  end

  reg transaction_processed;
  wire rw_bit = dataBuffer[15];
  wire [6:0] address_bits = dataBuffer[14:8];
  wire [7:0] data_bits = dataBuffer[7:0];
  // logic for processing transaction
  always @(posedge clk or negedge rst_n) begin
    if(~rst_n) begin
      transaction_processed <= 1'b0;
      rw_bit <= 1'b0;
      address_bits <= 7'b0;
      data_bits <= 8'b0;
    end else if (transaction_complete && ~transaction_processed) begin
      // writes are ignored
      if(rw_bit == READ) begin
        // any address greater than 0x04 is ignored
        if(address_bits <= MAX_ADDRESS) begin
          case (data_bits)
            7'h00 : en_reg_out_7_0  <= data_bits;
            7'h01 : en_reg_out_15_8 <= data_bits;
            7'h02 : en_reg_pwm_7_0  <= data_bits;
            7'h03 : en_reg_pwm_15_8 <= data_bits;
            7'h04 : pwm_duty_cycle  <= data_bits;
          endcase
        end
      end
      transaction_processed <= 1'b1;
    end else if (~transaction_complete && transaction_processed) begin
      transaction_processed <= 1'b0;
    end
  end

  

  // All output pins must be assigned. If not used, assign to 0.
  // Add this inside the module block
  assign uio_oe = 8'hFF; // Set all IOs to output

  // Add uio_in and ui_in[7:3] to the list of unused signals:
  wire _unused = &{ena, ui_in[7:3], uio_in, 1'b0};

endmodule
