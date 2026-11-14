// Leaky integrate-and-fire neuron, bit-exact with snn2gds/quant.py::int_forward.
//
//   s_prev = U > THETA
//   U     <= wrap_BU( U + ((-U) >>> K) + I - (s_prev ? THETA : 0) )
//   spike  = U > THETA          (combinational from the register)
//
// (-U) >>> K == -ceil(U / 2^K), which is what snnTorch's Leaky computes when its
// membrane is floored to the 2^-f grid after every update.
module snn_lif #(
    parameter integer BU    = 16,   // membrane bits
    parameter integer IW    = 12,   // input current bits
    parameter integer K     = 3,    // leak shift: beta = 1 - 2^-K
    parameter integer THETA = 16    // threshold (integer units)
) (
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 clear,
    input  wire                 en,
    input  wire signed [IW-1:0] I,
    output wire                 spike
);
    localparam integer XW = ((BU > IW) ? BU : IW) + 3;

    reg  signed [BU-1:0] U;
    wire signed [XW-1:0] u_x   = U;
    wire signed [XW-1:0] i_x   = I;
    wire signed [XW-1:0] neg_u = -u_x;
    wire signed [XW-1:0] leak  = neg_u >>> K;
    wire signed [XW-1:0] thr   = spike ? THETA : 0;
    wire signed [XW-1:0] nxt   = u_x + leak + i_x - thr;

    assign spike = (U > $signed(THETA));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      U <= {BU{1'b0}};
        else if (clear)  U <= {BU{1'b0}};
        else if (en)     U <= nxt[BU-1:0];
    end
endmodule
