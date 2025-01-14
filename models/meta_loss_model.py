import torch
import torch.nn as nn
import math
import torch.nn.functional as F


class MetaStepLossNetwork(nn.Module):
    def __init__(self, num_loss_hidden, num_loss_layers):
        super().__init__()
        self.layers = nn.ModuleList()
        for _ in range(num_loss_layers-1):
            self.layers.append(nn.Sequential(
                nn.Linear(num_loss_hidden, num_loss_hidden, bias=True),
                nn.ReLU()
            ))
        self.layers.append(nn.Linear(num_loss_hidden, 1, bias=True))

    def forward(self, x):
        for layer in self.layers:
            x = layer(x)
        return x


class MetaLossNetwork(nn.Module):
    def __init__(self, num_inner_steps, num_loss_hidden, num_loss_layers, use_step_loss):
        super().__init__()
        self.loss_layers = nn.ModuleList()
        self.use_step_loss = use_step_loss
        if self.use_step_loss:
            for _ in range(num_inner_steps):
                self.loss_layers.append(MetaStepLossNetwork(
                    num_loss_hidden, num_loss_layers))
        else:
            self.loss_layers.append(MetaStepLossNetwork(
                num_loss_hidden, num_loss_layers))

    def forward(self, x, step):
        if self.use_step_loss:
            x = self.loss_layers[step](x)
        else:
            x = self.loss_layers[0](x)
        return x


class MetaTaskLstmNetwork(nn.Module):
    def __init__(self, input_size, lstm_hidden, num_lstm_layers, lstm_out=0, device="cpu", use_softmax=False):
        super().__init__()
        if lstm_out == 0:
            lstm_out_size = lstm_hidden
        else:
            lstm_out_size = lstm_out
        self.embedding = nn.Embedding(7, input_size)
        self.h0 = nn.Parameter(torch.randn(num_lstm_layers,  lstm_out_size))
        self.c0 = nn.Parameter(torch.randn(num_lstm_layers,  lstm_hidden))
        self.lstm = nn.LSTM(
            batch_first=True, input_size=input_size, hidden_size=lstm_hidden, num_layers=num_lstm_layers, proj_size=lstm_out)
        self.device = device
        self.out_net = nn.Linear(lstm_out_size, 1)
        self.use_softmax = use_softmax

    def forward(self, x):
        x = x.long()
        mask = (x == 0)
        x = self.embedding(x)
        b, t, _ = x.shape
        h0 = self.h0.repeat(b, 1, 1).permute(1, 0, 2).contiguous()
        c0 = self.c0.repeat(b, 1, 1).permute(1, 0, 2).contiguous()
        lstm_out, (hidden, c) = self.lstm(x, (h0, c0))

        if self.use_softmax:
            return F.softmax(self.out_net(lstm_out).squeeze().masked_fill_(mask, float('-98765')), dim=1)
        else:
            return torch.abs(self.out_net(lstm_out).squeeze())


class MetaTaskMLPNetwork(nn.Module):
    def __init__(self, num_loss_weight_dims, use_softmax=False):
        super().__init__()
        self.mlp = nn.Sequential(
            nn.Linear(num_loss_weight_dims,
                      num_loss_weight_dims, bias=True),
            nn.ReLU(),
            nn.Linear(num_loss_weight_dims, 1, bias=True),
        )
        self.use_softmax = use_softmax

    def forward(self, x):
        mask = (x == 0)
        if self.use_softmax:
            return F.softmax(self.mlp(x).squeeze().masked_fill_(mask, float('-98765')), dim=1)
        else:
            return torch.abs(self.mlp(x).squeeze())
