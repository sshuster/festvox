from nnmnkwii.datasets import FileSourceDataset, FileDataSource
from os.path import join, expanduser
from collections import defaultdict
import numpy as np
import torch
from .audio import *
import sys,os

from torch.utils.data import Dataset
from torch.utils.data import DataLoader

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def assure_path_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
        print("Made the directory ", path) 

def plot_alignment(alignment, path, info=None):
  fig, ax = plt.subplots()
  im = ax.imshow(
    alignment,
    aspect='auto',
    origin='lower',
    interpolation='none')
  fig.colorbar(im, ax=ax)
  xlabel = 'Decoder timestep'
  if info is not None:
    xlabel += '\n\n' + info
  plt.xlabel(xlabel)
  plt.ylabel('Encoder timestep')
  plt.tight_layout()
  plt.savefig(path, format='png')
  plt.close()

def make_phids_phseq(file):
    ph_ids =  defaultdict(lambda: len(ph_ids))
    f = open(file)
    for line in f:
        line = line.split('\n')[0].split()[1:]
        for ph in line:
            _ = ph_ids[ph]
    return ph_ids

def make_phids(file):
    ph_ids =  defaultdict(lambda: len(ph_ids))
    f = open(file)
    for line in f:
        line = line.split('\n')[0].split('|')[-1].split()
        for ph  in line:
            _ = ph_ids[ph]
    return ph_ids    

def update_phids(ph_ids, file):
    f = open(file)
    for line in f:
        line = line.split('\n')[0].split('|')[-1].split()
        for tone in line:
            _ = ph_ids[tone]
    return ph_ids    

def make_charids(file):
    char_ids =  defaultdict(lambda: len(char_ids))
    char_ids['UNK']
    f = open(file)
    for line in f:
        line = line.split('\n')[0].split('|')[-1]
        for char in line:
            _ = char_ids[char]
    return char_ids    

def make_charids_tdd(file):
    char_ids =  defaultdict(lambda: len(char_ids))
    f = open(file)
    for line in f:
        line = '< ' + ''.join(k for k in line.split('\n')[0].split()[1:]) + ' >'
        for char in line:
            _ = char_ids[char]
    return char_ids


def update_charids(char_ids, file):
    f = open(file)
    for line in f:
        line = line.split('\n')[0].split('|')[-1].split()
        for char in line:
            _ = char_ids[char]
    return char_ids    

def get_padded_1d(seq):
    lengths = [len(x) for x in seq]
    max_len = np.max(lengths)
    return _pad(seq, max_len)
 

def _pad(seq, max_len):
    #print("Shape of seq: ", seq.shape, " and the max length: ", max_len)     
    assert len(seq) < max_len
    return np.pad(seq, (0, max_len - len(seq)),
                  mode='constant', constant_values=0)


def _pad_2d(x, max_len):
    x = np.pad(x, [(0, max_len - len(x)), (0, 0)],
               mode="constant", constant_values=0)
    return x

def save_checkpoint(model, optimizer, step, checkpoint_dir, epoch):
    checkpoint_path = join(
        checkpoint_dir, "checkpoint_step{}.pth".format(step))
    torch.save({
        "state_dict": model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "global_step": step,
        "global_epoch": epoch,
    }, checkpoint_path)
    print("Saved checkpoint:", checkpoint_path)

def save_states(global_step, mel_outputs, linear_outputs, attn, y,
                input_lengths, checkpoint_dir=None):
    print("Save intermediate states at step {}".format(global_step))

    # idx = np.random.randint(0, len(input_lengths))
    idx = min(1, len(input_lengths) - 1)
    input_length = input_lengths[idx]

    # Alignment
    path = join(checkpoint_dir, "step{}_alignment.png".format(
        global_step))
    # alignment = attn[idx].cpu().data.numpy()[:, :input_length]
    alignment = attn[idx].cpu().data.numpy()
    save_alignment(path, alignment, global_step)

    # Predicted spectrogram
    path = join(checkpoint_dir, "step{}_predicted_spectrogram.png".format(
        global_step))
    linear_output = linear_outputs[idx].cpu().data.numpy()
    save_spectrogram(path, linear_output)

    # Predicted audio signal
    signal = inv_spectrogram(linear_output.T)
    path = join(checkpoint_dir, "step{}_predicted.wav".format(
        global_step))
    save_wav(signal, path)

    # Target spectrogram
    path = join(checkpoint_dir, "step{}_target_spectrogram.png".format(
        global_step))
    linear_output = y[idx].cpu().data.numpy()
    save_spectrogram(path, linear_output)


def save_alignment(path, attn, global_step):
    plot_alignment(attn.T, path, info="tacotron, step={}".format(global_step))


def save_spectrogram(path, linear_output):
    spectrogram = denormalize(linear_output)
    plt.figure(figsize=(16, 10))
    plt.imshow(spectrogram.T, aspect="auto", origin="lower")
    plt.colorbar()
    plt.tight_layout()
    plt.savefig(path, format="png")
    plt.close()


def learning_rate_decay(init_lr, global_step):
    warmup_steps = 4000.0
    step = global_step + 1.
    lr = init_lr * warmup_steps**0.5 * np.minimum(
        step * warmup_steps**-1.5, step**-0.5)
    return lr

class DataSource(object):

    def collect_files(self):
        raise NotImplementedError

    def collect_features(self, *args):
        raise NotImplementedError

class FalconDataSource(object):

    def collect_files(self):
        raise NotImplementedError

    def collect_features(self, *args):
        raise NotImplementedError

class FeatDataSource(FalconDataSource):

    def __init__(self, tdd_file, data_dir):
        self.tdd_file = tdd_file

    def collect_files(self):
        pass

def get_fnames(fnames_file):
    filenames_array = []
    f = open(fnames_file)
    for line in f:
      line = line.split('\n')[0]
      filenames_array.append(line)
    return filenames_array

def populate_featdict(desc_file):
    f = open(desc_file)
    dict = {}
    dict_featnames = {}
    idx = 0
    for line in f:
       line = line.split('\n')[0] 
       name, length, type = line.split('|')[0], line.split('|')[1], line.split('|')[2]
       dict[name + '_length'] = length
       dict[name + '_type'] = type
       dict_featnames[idx] = name
       idx += 1
    return dict, dict_featnames


class CombinedDataSource(Dataset):
  
  def __init__(self, list):
      self.list = list
      self.num_sets = len(list)
      
  def __len__(self):
      assert len(self.list[0]) == len(self.list[1])
      return len(self.list[0])
    
  def __getitem__(self, idx):
      return [k[idx] for k in self.list]

  def get_nsets(self):
      return self.num_sets
  

class CategoricalDataSource_v1(Dataset):
    '''Syntax
    dataset = CategoricalDataSource(fnames.txt.train, etc/falcon_feats.desc, festival/falcon_feats) 

    '''

    def __init__(self, fnames_file, desc_file, feats_dir):
      self.fnames_file = fnames_file
      self.feats_dir = feats_dir
      self.desc_file = desc_file
      self.filenames_array = get_fnames(self.fnames_file)
      self.dict_featmetas, self.dict_featnames = populate_featdict(self.desc_file)

    def __getitem__(self, idx):
        fname = self.filenames_array[idx]
        f = open(self.feats_dir + '/' + fname + '.feats')
        phones = []
        for line in f:
           line = line.split('\n')[0]
           feats = line.split('|')
           if len(feats) > 1:
              print("Cannot handle multiple feats for now")
              sys.exit()
           phones.append(line)
        print("Length of phones: ", len(phones))
        return phones

    def __len__(self):
        return len(self.filenames_array)

def get_featmetainfo(desc_file, feat_name):

    f = open(desc_file)
    for line in f:
        line = line.split('\n')[0]
        feat = line.split('|')[0]
        if feat_name == feat:
           feat_length, feat_type = line.split('|')[1], line.split('|')[2]
           return feat_length,feat_type 

def populate_featarray(fname, feats_dir, feats_dict):
    feats_array = []
    f = open(fname)
    for line in f:
        line = line.split('\n')[0]
        feats  = line.split()
        for feat in feats:
            feats_array.append(feats_dict[feat])
    feats_array = np.array(feats_array)
    return feats_array

class CategoricalDataSource(Dataset):
    '''Syntax
    dataset = CategoricalDataSource(fnames.txt.train, etc/falcon_feats.desc, feat_name, feats_dir)

    '''

    def __init__(self, fnames_file, desc_file, feat_name, feats_dir, feats_dict = None):
      self.fnames_file = fnames_file
      self.feat_name = feat_name
      self.desc_file = desc_file
      self.filenames_array = get_fnames(self.fnames_file)
      self.feat_length, self.feat_type = get_featmetainfo(self.desc_file, feat_name)
      self.feats_dir = feats_dir
      self.feats_dict = defaultdict(lambda: len(self.feats_dict)) if feats_dict is None else feats_dict

    def __getitem__(self, idx):

        assert self.feat_type == 'categorical'
        fname = self.filenames_array[idx]
        fname = self.feats_dir + '/' + fname + '.feats'
        feats_array = populate_featarray(fname, self.feats_dir, self.feats_dict) 
        return feats_array

    def __len__(self):
        return len(self.filenames_array)


class FloatDataSource(Dataset):
    '''Syntax
    dataset = CategoricalDataSource(fnames.txt.train, etc/falcon_feats.desc, feat_name, feats_dir)

    '''

    def __init__(self, fnames_file, desc_file, feat_name, feats_dir, feats_dict = None):
      self.fnames_file = fnames_file
      self.feat_name = feat_name
      self.desc_file = desc_file
      self.filenames_array = get_fnames(self.fnames_file)
      self.feat_length, self.feat_type = get_featmetainfo(self.desc_file, feat_name)
      self.feats_dir = feats_dir
      self.feats_dict = defaultdict(lambda: len(self.feats_dict)) if feats_dict is None else feats_dict

    def __getitem__(self, idx):

        fname = self.filenames_array[idx]
        fname = self.feats_dir + '/' + fname + '.feats.npy'
        feats_array = np.load(fname)
        return feats_array

    def __len__(self):
        return len(self.filenames_array)


def collate_fn_1d(batch):
    """Create batch"""

    input_lengths = [len(x) for x in batch]
    max_input_len = np.max(input_lengths) + 1

    a = np.array([_pad(x, max_input_len) for x in batch], dtype=np.int)
    x_batch = torch.LongTensor(a)

    return x_batch


def collate_fn_float(batch):
    """Create batch"""

    # Check dimensions and send to collate_fn_1d if 1d. Need to worry about long tensor but we will ignore this for now
    if len(batch[0].shape) < 2:
        return collate_fn_1d(batch)

    input_lengths = [x.shape[0] for x in batch]
    max_input_len = np.max(input_lengths) + 1

    a = np.array([_pad_2d(x, max_input_len) for x in batch], dtype=np.int)
    x_batch = torch.FloatTensor(a)

    return x_batch

class CombinedDataset(Dataset):
   
    def __init__(self, list):
        self.list = list
        assert len(list[0]) == len(list[1])

    def combine_datasets(self):
        num_sets = len(self.list)
        
    def __len__(self):
       return len(self.list[0])

    def __getitem__(self, idx):
       return [k[idx] for k in self.list]


def collate_fn_combined(batch):
    num_sets = len(batch[0])
    batches = []
    print("The number of sets", num_sets)
    for n in range(num_sets):
        dim = len(batch[0][n].shape)
        print("Processing set ", n, "Dimensions are ", dim)
        batch1 = get_padded_1d(batch[:][n])
        batches.append(torch.tensor(batch1))
    return batches

class TextDataSource(DataSource):

    def __init__(self, data_dir, charids, tdd_file):
        self.charids = charids
        self.data_dir = data_dir
        self.tdd_file = tdd_file

    def collect_files(self):
        meta = join(self.data_dir, self.tdd_file)
        with open(meta, "rb") as f:
            lines = f.readlines()
        lines = list(map(lambda l: l.decode("utf-8").split("|")[-1], lines))
        return lines

    def collect_features(self, text):
        #print("I got this as text: ", text)
        #print(self.charids)
        #sys.exit()
        text_ids = ' '.join(str(self.charids[k]) for k in text.strip()).split()
        return np.asarray(text_ids,
                          dtype=np.int32)

    def get_charids(self):
        return self.charids

class PhoneDataSource(DataSource):

    def __init__(self, data_dir, charids, phseq_file):
        self.charids = defaultdict(lambda: len(self.charids))
        self.charids = charids
        self.data_dir = data_dir
        self.phseq_file = phseq_file

    def collect_files(self):
        meta = join(self.data_dir, self.phseq_file)
        with open(meta, "rb") as f:
            lines = f.readlines()
        lines = list(map(lambda l: l.decode("utf-8").split("|")[-1], lines))
        return lines

    def collect_features(self, text):
        text_ids = ' '.join(str(self.charids[k]) for k in text.split()).split()
        return np.asarray(text_ids,
                          dtype=np.int32)

    def get_charids(self):
        return self.charids

class ToneDataSource(DataSource):

    def __init__(self, data_dir, charids):
        #self.charids = defaultdict(lambda: len(self.charids))
        self.charids = charids
        self.data_dir = data_dir

    def collect_files(self):
        meta = join(self.data_dir, "txt.done.data.interpolatedtones")
        with open(meta, "rb") as f:
            lines = f.readlines()
        lines = list(map(lambda l: l.decode("utf-8").split("|")[1], lines))
        return lines

    def collect_features(self, text):
        text_ids = ' '.join(str(self.charids[k]) for k in text.split()).split()
        return np.asarray(text_ids,
                          dtype=np.int32)

    def get_charids(self):
        return self.charids

class _NPYDataSource(DataSource):
    def __init__(self, data_dir, col, tdd_file):
        self.col = col
        self.data_dir = data_dir
        self.tdd_file = tdd_file

    def collect_files(self):
        meta = join(self.data_dir, self.tdd_file)
        with open(meta, "rb") as f:
            lines = f.readlines()
        lines = list(map(lambda l: l.decode("utf-8").split("|")[self.col], lines))
        paths = list(map(lambda f: join(f), lines))
        return paths

    def collect_features(self, path):
        #print("Trying to collect features from ", self.data_dir)
        return np.load(path)


class MelSpecDataSource(_NPYDataSource):
    def __init__(self, data_dir, tdd_file):
        super(MelSpecDataSource, self).__init__(data_dir, 1, tdd_file)


class LinearSpecDataSource(_NPYDataSource):
    def __init__(self, data_dir, tdd_file):
        super(LinearSpecDataSource, self).__init__(data_dir, 0, tdd_file)


class PyTorchDataset(object):
    def __init__(self, X, Mel, Y):
        self.X = X
        self.Mel = Mel
        self.Y = Y

    def __getitem__(self, idx):
        return self.X[idx], self.Mel[idx], self.Y[idx]

    def __len__(self):
        return len(self.X)

class PyTorchDataset_tones(object):
    def __init__(self, X, Mel, Y, tones):
        self.X = X
        self.Mel = Mel
        self.Y = Y
        self.tones = tones

    def __getitem__(self, idx):
        try:
           assert len(self.X[idx]) > len(self.tones[idx])
        except AssertionError:
           k = self.tones[idx]
           k = k[0:len(self.X[idx])]
           return self.X[idx], k, self.Mel[idx], self.Y[idx]
           print("Shapes of input and tones: ", self.X[idx].shape, self.tones[idx].shape)
        return self.X[idx], self.tones[idx], self.Mel[idx], self.Y[idx]

    def __len__(self):
        return len(self.X)


def collate_fn(batch):
    """Create batch"""
    r = 5
    input_lengths = [len(x[0]) for x in batch]
    max_input_len = np.max(input_lengths) + 1
    # Add single zeros frame at least, so plus 1
    max_target_len = np.max([len(x[1]) for x in batch]) + 1
    if max_target_len % r != 0:
        max_target_len += r - max_target_len % r
        assert max_target_len % r == 0

    a = np.array([_pad(x[0], max_input_len) for x in batch], dtype=np.int)
    x_batch = torch.LongTensor(a)

    input_lengths = torch.LongTensor(input_lengths)

    b = np.array([_pad_2d(x[1], max_target_len) for x in batch],
                 dtype=np.float32)
    mel_batch = torch.FloatTensor(b)

    c = np.array([_pad_2d(x[2], max_target_len) for x in batch],
                 dtype=np.float32)
    y_batch = torch.FloatTensor(c)
    return x_batch, input_lengths, mel_batch, y_batch



def collate_fn_tones(batch):
    """Create batch"""
    #print(batch[0])
    r = hparams.outputs_per_step
    input_lengths = [len(x[0]) for x in batch]
    max_input_len = np.max(input_lengths) + 1
    tone_lengths = [len(x[1]) for x in batch]
    max_tone_len  =  np.max(tone_lengths)

    '''Sai Krishna Rallabandi
    ########### Handle this better 29 May 2019 ###########
    try:
      assert max_input_len == max_tone_len
    except AssertionError:
      print("Max Length of inputs: ", max_input_len, " while that of tones: ", max_tone_len)
      sys.exit()
    ######################################################
    '''

    # Add single zeros frame at least, so plus 1
    max_target_len = np.max([len(x[2]) for x in batch]) + 1
    if max_target_len % r != 0:
        max_target_len += r - max_target_len % r
        assert max_target_len % r == 0


    a = np.array([_pad(x[0], max_input_len) for x in batch], dtype=np.int)
    x_batch = torch.LongTensor(a)

    a_tone = np.array([_pad(x[1], max_input_len) for x in batch], dtype=np.int)
    xtone_batch = torch.LongTensor(a_tone)

    input_lengths = torch.LongTensor(input_lengths)

    b = np.array([_pad_2d(x[2], max_target_len) for x in batch],
                 dtype=np.float32)
    mel_batch = torch.FloatTensor(b)

    c = np.array([_pad_2d(x[3], max_target_len) for x in batch],
                 dtype=np.float32)
    y_batch = torch.FloatTensor(c)
    #print("Returning a batch", x_batch.shape, xtone_batch.shape, input_lengths)
    return x_batch, xtone_batch, input_lengths, mel_batch, y_batch


