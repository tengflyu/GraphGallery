import tensorflow as tf
from tensorflow.keras import Model, Input
from tensorflow.keras.layers import Dense, Dropout
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import regularizers

from graphgallery.nn.layers import GraphConvolution
from graphgallery.nn.models import SemiSupervisedModel
from graphgallery.sequence import FastGCNBatchSequence
from graphgallery.utils.shape_utils import set_equal_in_length
from graphgallery import astensors, asintarr, normalize_x, normalize_adj, Bunch


class FastGCN(SemiSupervisedModel):
    """
        Implementation of Fast Graph Convolutional Networks (FastGCN).
        `FastGCN: Fast Learning with Graph Convolutional Networks via Importance Sampling <https://arxiv.org/abs/1801.10247>`
        Tensorflow 1.x implementation: <https://github.com/matenure/FastGCN>

        Arguments:
        ----------
            adj: shape (N, N), Scipy sparse matrix if  `is_adj_sparse=True`,
                Numpy array-like (or matrix) if `is_adj_sparse=False`.
                The input `symmetric` adjacency matrix, where `N` is the number
                of nodes in graph.
            x: shape (N, F), Scipy sparse matrix if `is_x_sparse=True`,
                Numpy array-like (or matrix) if `is_x_sparse=False`.
                The input node feature matrix, where `F` is the dimension of features.
            labels: Numpy array-like with shape (N,)
                The ground-truth labels for all nodes in graph.
            norm_adj (Float scalar, optional):
                The normalize rate for adjacency matrix `adj`. (default: :obj:`-0.5`,
                i.e., math:: \hat{A} = D^{-\frac{1}{2}} A D^{-\frac{1}{2}})
            norm_x (String, optional):
                How to normalize the node feature matrix. See `graphgallery.normalize_x`
                (default :obj: `None`, i.e., do not enforce normalize)
            batch_size (Positive integer, optional):
                Batch size for the training nodes. (default :int: `256`)
            rank (Positive integer, optional):
                The selected nodes for each batch nodes, `rank` must be smaller than
                `batch_size`. (default :int: `100`)
            device (String, optional):
                The device where the model is running on. You can specified `CPU` or `GPU`
                for the model. (default: :str: `CPU:0`, i.e., running on the 0-th `CPU`)
            seed (Positive integer, optional):
                Used in combination with `tf.random.set_seed` & `np.random.seed` & `random.seed`
                to create a reproducible sequence of tensors across multiple calls.
                (default :obj: `None`, i.e., using random seed)
            name (String, optional):
                Specified name for the model. (default: :str: `class.__name__`)


    """

    def __init__(self, adj, x, labels, norm_adj=-0.5, norm_x=None,
                 batch_size=256, rank=100, device='CPU:0', seed=None, name=None, **kwargs):

        super().__init__(adj, x, labels, device=device, seed=seed, name=name, **kwargs)

        self.rank = rank
        self.batch_size = batch_size
        self.norm_adj = norm_adj
        self.norm_x = norm_x
        self.preprocess(adj, x)

    def preprocess(self, adj, x):
        super().preprocess(adj, x)
        adj, x = self.adj, self.x

        if self.norm_adj:
            adj = normalize_adj(adj, self.norm_adj)

        if self.norm_x:
            x = normalize_x(x, norm=self.norm_x)

        x = adj.dot(x)

        with tf.device(self.device):
            self.x_norm, self.adj_norm = astensors(x), adj

    def build(self, hiddens=[32], activations=['relu'], dropouts=[0.5], l2_norms=[5e-4],
              lr=0.01, use_bias=False):

        ############# Record paras ###########
        local_paras = locals()
        local_paras.pop('self')
        paras = Bunch(**local_paras)
        hiddens, activations, dropouts, l2_norms = set_equal_in_length(hiddens, activations, dropouts, l2_norms)
        paras.update(Bunch(hiddens=hiddens, activations=activations, dropouts=dropouts, l2_norms=l2_norms))
        # update all parameters
        self.paras.update(paras)
        self.model_paras.update(paras)
        ######################################

        with tf.device(self.device):

            x = Input(batch_shape=[None, self.n_features], dtype=self.floatx, name='features')
            adj = Input(batch_shape=[None, None], dtype=self.floatx, sparse=True, name='adj_matrix')

            h = x
            for hid, activation, dropout, l2_norm in zip(hiddens, activations, dropouts, l2_norms):
                h = Dense(hid, use_bias=use_bias, activation=activation,
                          kernel_regularizer=regularizers.l2(l2_norm))(h)
                h = Dropout(rate=dropout)(h)

            output = GraphConvolution(self.n_classes, use_bias=use_bias, activation='softmax')([h, adj])

            model = Model(inputs=[x, adj], outputs=output)
            model.compile(loss='sparse_categorical_crossentropy', optimizer=Adam(lr=lr), metrics=['accuracy'])
            self.model = model

    def predict(self, index):
        super().predict(index)
        index = asintarr(index)
        adj = self.adj_norm[index]
        with tf.device(self.device):
            adj = astensors(adj)
            logit = self.model.predict_on_batch([self.x_norm, adj])

        if tf.is_tensor(logit):
            logit = logit.numpy()
        return logit

    def train_sequence(self, index):
        index = asintarr(index)
        labels = self.labels[index]
        adj = self.adj[index].tocsc(copy=False)[:, index]

        if self.norm_adj:
            adj = normalize_adj(adj, self.norm_adj)

        with tf.device(self.device):
            x = tf.gather(self.x_norm, index)
            sequence = FastGCNBatchSequence([x, adj], labels,
                                            batch_size=self.batch_size,
                                            rank=self.rank)
        return sequence

    def test_sequence(self, index):
        index = asintarr(index)
        labels = self.labels[index]
        adj = self.adj_norm[index]

        with tf.device(self.device):
            sequence = FastGCNBatchSequence([self.x_norm, adj],
                                            labels, batch_size=None, rank=None)  # use full batch
        return sequence