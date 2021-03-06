import tensorflow as tf


from graphgallery.nn.models import SemiSupervisedModel
from graphgallery.sequence import FullBatchNodeSequence
from graphgallery.utils.decorators import EqualVarLength

from graphgallery.nn.models import GCN
from graphgallery.nn.models.semisupervised.tf_models.gcna import GCNA as tfGCNA

from graphgallery import transforms as T


class GCNA(GCN):
    """
    GCN + attribute matrix

    Implementation of Graph Convolutional Networks(GCN) concated with attribute matrix.
    `Semi - Supervised Classification with Graph Convolutional Networks 
    <https://arxiv.org/abs/1609.02907>`
    GCN Tensorflow 1.x implementation: <https://github.com/tkipf/gcn>
    GCN Pytorch implementation: <https://github.com/tkipf/pygcn>

    """

    def __init__(self, *graph, adj_transform="normalize_adj", attr_transform=None,
                 device='cpu:0', seed=None, name=None, **kwargs):
        """Create a Graph Convolutional Networks(GCN) model 
            concated with attribute matrix (GCNA).

        This can be instantiated in several ways:

            model = GCNA(graph)
                with a `graphgallery.data.Graph` instance representing
                A sparse, attributed, labeled graph.

            model = GCNA(adj_matrix, attr_matrix, labels)
                where `adj_matrix` is a 2D Scipy sparse matrix denoting the graph,
                 `attr_matrix` is a 2D Numpy array - like matrix denoting the node
                 attributes, `labels` is a 1D Numpy array denoting the node labels.

        Parameters:
        ----------
        graph: An instance of `graphgallery.data.Graph` or a tuple(list) of inputs.
            A sparse, attributed, labeled graph.
        adj_transform: string, `transform`, or None. optional
            How to transform the adjacency matrix. See `graphgallery.transforms`
            (default:: obj: `'normalize_adj'` with normalize rate `- 0.5`.
            i.e., math: : \hat{A} = D^{-\frac{1}{2}} A D^{-\frac{1}{2}})
        attr_transform: string, `transform`, or None. optional
            How to transform the node attribute matrix. See `graphgallery.transforms`
            (default: obj: `None`)
        device: string. optional
            The device where the model is running on. You can specified `CPU` or `GPU`
            for the model. (default: : str: `CPU: 0`, i.e., running on the 0-th `CPU`)
        seed: interger scalar. optional
            Used in combination with `tf.random.set_seed` & `np.random.seed`
            & `random.seed` to create a reproducible sequence of tensors across
            multiple calls. (default: obj: `None`, i.e., using random seed)
        name: string. optional
            Specified name for the model. (default:: str: `class.__name__`)
        kwargs: other customized keyword Parameters.
        """
        super().__init__(*graph,
                         adj_transform=adj_transform, attr_transform=attr_transform,
                         device=device, seed=seed, name=name, **kwargs)

    # use decorator to make sure all list arguments have the same length
    @EqualVarLength()
    def build(self, hiddens=[16], activations=['relu'], dropout=0.5,
              l2_norm=5e-4, lr=0.01, use_bias=False):

        if self.kind == "T":
            with tf.device(self.device):
                self.model = tfGCNA(self.graph.n_attrs, self.graph.n_classes, hiddens=hiddens,
                                activations=activations, dropout=dropout, l2_norm=l2_norm,
                                lr=lr, use_bias=use_bias)
        else:
            raise NotImplementedError