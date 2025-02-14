###############################################################################
# Copyright (C) 2020-2021 Habana Labs, Ltd. an Intel Company
###############################################################################

import torch
import os
from glob import glob
import habana_frameworks.torch.core

torch.ops.load_library(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'build/lib.*/*.so'))[0])

class FusedSoftmaxFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input, mask, dim):
        # ctx is a context object that can be used to stash information
        # for backward computation
        tensor = torch.ops.custom_op.fusedsoftmax(input, mask, dim)
        ctx.y = tensor
        ctx.dim = dim
        return tensor

    @staticmethod
    def backward(ctx, grad_output):
        if grad_output is None:
            return None
        y = ctx.y
        ctx.y = None
        dim = ctx.dim
        ctx.dim = None
        grad_input = torch.ops.custom_op.fusedsoftmax_backward(y, grad_output, dim)
        return grad_input, None, None

class FusedSoftmaxBiasFunction(torch.autograd.Function):
    @staticmethod
    def forward(ctx, input, mask, bias, dim):
        # ctx is a context object that can be used to stash information
        # for backward computation
        tensor = torch.ops.custom_op.fusedsoftmax_bias(input, mask, bias, dim)
        ctx.y = tensor
        ctx.dim = dim
        ctx.use_bias = False
        if bias is not None:
            ctx.use_bias = True
        return tensor

    @staticmethod
    def backward(ctx, grad_output):
        if grad_output is None:
            return None
        y = ctx.y
        ctx.y = None
        dim = ctx.dim
        ctx.dim = None
        grad_input = torch.ops.custom_op.fusedsoftmax_backward(y, grad_output, dim)

        grad_bias = None
        if ctx.use_bias:
            grad_bias = torch.sum(grad_input, dim=-4, keepdim=True)

        return grad_input, None, grad_bias, None


ENABLE_OPT = True

def fused_softmax(input, mask, dim):
    if ENABLE_OPT and input[..., :, :1, :1, :].shape == mask.shape:
        return FusedSoftmaxFunction.apply(input, mask, dim)
    else:
        input += mask
        return torch.softmax(input, dim=dim)

def fused_softmax_bias(input, mask, bias, dim):
    if ENABLE_OPT and input[..., :, :1, :1, :].shape == mask.shape and input[..., :1, :, :, :].shape == bias.shape:
        return FusedSoftmaxBiasFunction.apply(input, mask, bias, dim)
    else:
        input += mask
        input += bias
        return torch.softmax(input, dim=dim)
