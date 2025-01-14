import torch
from torch import nn
import torch.nn.functional as F
import pytorch_lightning as pl
from torch.optim.lr_scheduler import ReduceLROnPlateau


class RecurrentAutoencoder(pl.LightningModule):  # nn.Module
    """
    Model:
    SEE: https://github.com/fabiozappo/LSTM-Autoencoder-Time-Series
    SEE: https://github.com/curiousily/Getting-Things-Done-with-Pytorch
    """

    def __init__(self, seq_len, n_features, embedding_dim=64, n_layers=1):
        super(RecurrentAutoencoder, self).__init__()

        # Params
        self.lr = 1e-2
        self.embedding_dim = embedding_dim

        # Layers
        self.encoder = Encoder(seq_len, n_features, embedding_dim, n_layers)
        self.decoder = Decoder(seq_len, embedding_dim, n_features, n_layers)

        self.custom_loss = nn.MSELoss()  # nn.L1Loss(reduction='sum')

    # def custom_loss(self, ae_input, ae_output):
    #     # l1 loss
    #     l1_loss = F.l1_loss(ae_input, ae_output, reduction='sum')
    #
    #     # maximize average cosine similarity
    #     # cos_sim = 0
    #     # for (b1, b2) in zip(ae_input, ae_output):
    #     #     cos_sim += 1 - F.cosine_similarity(b1, b2).mean()
    #
    #     # # loss end
    #     # l1_loss_end = F.l1_loss(
    #     #     ae_input, ae_output, reduction='none')[:, -1, :].sum()
    #     #
    #     # # loss start
    #     # l1_loss_start = F.l1_loss(
    #     #     ae_input, ae_output, reduction='none')[:, 0, :].sum()
    #
    #     # additional penalty for the max l1
    #     # l1_loss_max = F.l1_loss(
    #     #     ae_input, ae_output, reduction='none').max()
    #
    #     # cos_sim +  # l1_loss # + l1_loss_max  # cos_sim
    #     # alpha = 0.8
    #     loss = l1_loss  # * alpha + (l1_loss_end + l1_loss_start) * (1 - alpha)
    #     return loss

    def forward(self, x):
        h = self.encoder(x)
        x = self.decoder(h)
        return x

    def training_step(self, batch, batch_idx):
        x = batch

        x_hat = self.forward(x)

        loss = self.custom_loss(x_hat, x)
        self.log('train_loss', loss)
        return loss

    def validation_step(self, batch, batch_idx):
        x = batch

        x_hat = self.forward(x)

        loss = self.custom_loss(x_hat, x)
        self.log('validation_loss', loss)
        return loss

    def test_step(self, batch, batch_idx):
        x = batch

        x_hat = self.forward(x)

        loss = self.custom_loss(x_hat, x)
        output = dict({
            'test_loss': loss
        })
        self.log('test_loss', loss)
        return output

    def configure_optimizers(self):
        optimizer = torch.optim.Adam(self.parameters(), lr=self.lr)
        return {
            "optimizer": optimizer,
            "lr_scheduler": {
                "scheduler": ReduceLROnPlateau(optimizer),
                "monitor": "validation_loss",
                "frequency": 1
            },
        }


class Encoder(pl.LightningModule):
    def __init__(self, seq_len, n_features, embedding_dim=64, n_layers=1):
        super(Encoder, self).__init__()

        self.seq_len, self.n_features = seq_len, n_features
        self.embedding_dim, self.hidden_dim = embedding_dim, 2 * embedding_dim

        self.rnn1 = nn.LSTM(
            input_size=n_features,
            hidden_size=self.hidden_dim,
            num_layers=n_layers,
            batch_first=True
        )

        self.rnn2 = nn.LSTM(
            input_size=self.hidden_dim,
            hidden_size=embedding_dim,
            num_layers=1,
            batch_first=True
        )

    def forward(self, x):
        batch_size = x.shape[0]
        x = x.reshape((batch_size, self.seq_len, self.n_features))

        x, (_, _) = self.rnn1(x)
        x, (hidden_n, _) = self.rnn2(x)

        return hidden_n.reshape((batch_size, self.embedding_dim))


class Decoder(pl.LightningModule):
    def __init__(self, seq_len, input_dim=64, n_features=1, n_layers=1):
        super(Decoder, self).__init__()

        self.seq_len, self.input_dim = seq_len, input_dim
        self.hidden_dim, self.n_features = 2 * input_dim, n_features

        self.rnn1 = nn.LSTM(
            input_size=input_dim,
            hidden_size=input_dim,
            num_layers=1,
            batch_first=True
        )

        self.rnn2 = nn.LSTM(
            input_size=input_dim,
            hidden_size=self.hidden_dim,
            num_layers=n_layers,
            batch_first=True
        )

        self.output_layer = nn.Linear(self.hidden_dim, n_features)

    def forward(self, x):
        batch_size = x.shape[0]

        x = x.repeat(self.seq_len, 1)

        x = x.reshape((batch_size, self.seq_len, self.input_dim))

        x, (hidden_n, cell_n) = self.rnn1(x)
        x, (hidden_n, cell_n) = self.rnn2(x)
        x = x.reshape((batch_size, self.seq_len, self.hidden_dim))

        return self.output_layer(x)
