
'''
INPUT_DATA_PATH_ contains the prokka and blast files generated by fabv_InputCreation.py
DATA_PATH_ is the output path. it is ok for both of them to be the same
'''

import os
from os.path import join as pjoin

import re

from multiprocessing import Pool
import subprocess

from Bio.Seq import Seq
from Bio import SeqIO, SeqFeature
from Bio.Blast import NCBIXML
from Bio.SeqRecord import SeqRecord
from Bio.Alphabet import IUPAC
from Bio.Alphabet import generic_dna

import pandas as pd 
import numpy as np

import textwrap
from timeit import default_timer as timer


def cat_Files(file_list, extension, DATA_PATH_, out_filename_path):
	'''
	General purpose function to cat thousands of files and delete the intermediate chunking files
	file_list must have the path joined to the name and also the file extension
	extension should be written without the <.> examples: <txt> <csv>
	DATA_PATH_ is the output directory for the chunks
	out_filename_path must have the path joined to the name but not the extension
	'''
	major_length = len(file_list) - len(file_list)%100  #get length to chunk that is divisble by 100
	i = 0
	while i < len(file_list):
		i2 = i
		i += 100
		if i == major_length:
			print('final', '   ', len(file_list[i2:])) #for tracking
			chunk = ' '.join(file_list[i2:])
			chunk_path = pjoin(DATA_PATH_, 'final_chunk')
			os.system('cat %s > %s.%s' % (chunk, chunk_path, extension))
			break
		chunk = ' '.join(file_list[i2:i])
		print(i, '   ', len(file_list[i2:i])) #for tracking
		chunk_path = pjoin(DATA_PATH_, '%s_chunk' % str(i))
		os.system('cat %s > %s.%s' % (chunk, chunk_path, extension))
	wild_chunk_path = pjoin(DATA_PATH_,'*_chunk.%s' % extension)
	os.system('cat %s > %s.%s' % (wild_chunk_path, out_filename_path, extension))
	os.system('rm %s' % wild_chunk_path)


def read_SeqType(input_seqtype):
	'''
	Specifies the prokka sequence type to search for a given homolog in and then write a fasta file using that
	sequence type.
	'''
	if input_seqtype == 'DNA':
		seq_extension = '.ffn'
	if input_seqtype == 'AA':
		seq_extension = '.faa'
	return(seq_extension)


def get_GetHomologsPATHS(INPUT_DATA_PATH_,DATA_PATH_,INPUT_QUERY_FASTA_FILE_,INPUT_QUERY_NAME_,INPUT_DF_):
	'''
	'''
# INPUT_DATA_PATH = '/Users/owlex/Dropbox/Documents/Northwestern/Hartmann_Lab/enr_comparison_project/tests/fabv_regs/test2'
# DATA_PATH = '/Users/owlex/Dropbox/Documents/Northwestern/Hartmann_Lab/enr_comparison_project/tests/fabv_regs/test2'
# INPUT_QUERY_FASTA_FILE = '/Users/owlex/Dropbox/Documents/Northwestern/Hartmann_Lab/enr_comparison_project/tests/fabv_regs/test_files/pao1_fabv.fasta'
# INPUT_QUERY_NAME = 'pao1_fabv'
	global INPUT_DATA_PATH,DATA_PATH,INPUT_QUERY_FASTA_FILE,INPUT_QUERY_NAME,INPUT_DF
	INPUT_DATA_PATH = INPUT_DATA_PATH_
	DATA_PATH = DATA_PATH_
	INPUT_QUERY_FASTA_FILE = INPUT_QUERY_FASTA_FILE_
	INPUT_QUERY_NAME = INPUT_QUERY_NAME_
	INPUT_DF = INPUT_DF_


def parallel_FindHomolog(cf,INPUT_DATA_PATH,INPUT_QUERY_FASTA,prokka_input,blast_input,blast_output,seq_extension):
	'''
	##Step1: blast for query
	##Step2: Format df_blast_cf hit table to also contain input_query_name and cleaned_filename
	##Step3: Retrieve all hits from the cf .faa 
	'''
	##Step1:Blasting for query
	#cf_db is the blast database tag. not a pandas dataframe
	cf_db = pjoin(blast_input,cf)
	#the hit.csv and sequences.txt files will use cf_blast_output as the basename
	cf_blast_output = pjoin(blast_output,cf)
	os.system('blastp -query %s -db %s -max_target_seqs 100 -evalue 1e-6 -outfmt "10 sseqid stitle mismatch positive gaps ppos pident qcovs evalue bitscore" -num_threads 1  -out %s.csv' % (INPUT_QUERY_FASTA_FILE, cf_db, cf_blast_output))
	##Step2:Formatting blast hit csv table
	#reading in hits csv output file
	col_names = ['sseqid','stitle','mismatch','positive','gaps','ppos','pident','qcovs','evalue','bitscore']
	df_blast_cf = pd.read_csv(cf_blast_output+'.csv',names=col_names)
	#adding INPUT_QUERY_NAME and cleaned_filename
	df_blast_cf['qseqid'] = INPUT_QUERY_NAME
	df_blast_cf['cleaned_filename'] = cf
	# dropping duplicate sseqids
	df_blast_cf = df_blast_cf.drop_duplicates(subset='sseqid',keep='first',inplace=False)
	##Step3:Retrieving all hits from the cf .faa from INPUT_DATA_PATH/prokka_input
	#cf filepath
	cf_prokka_faa = pjoin(INPUT_DATA_PATH,prokka_input,cf)
	#list of sseqids to find
	sseqid_list = df_blast_cf['sseqid'].tolist()
	##checking that sseqid_list actually has sseqids. if it does then proceed
	if len(sseqid_list) > 0:
		#writing sequences to temp_blast_output
		with open(cf_blast_output+seq_extension,'w') as outfile:
			#using SeqIO to parse .faa file
			for record in SeqIO.parse(cf_prokka_faa+seq_extension,'fasta'):
				if record.id in sseqid_list:
					outfile.write('>%s\n'%(record.id))
					concatseq = textwrap.wrap(str(record.seq),60,break_on_hyphens=False)
					[outfile.write('%s\n'%i) for i in concatseq]
					#outfile.write('>%s\n%s\n'%(record.id,str(record.seq)))
					sseqid_list.remove(record.id)
					if len(sseqid_list) < 1: break
		#saving the df with the same name as before, cf_blast_output. No index or headers for later concatenation
		df_blast_cf.to_csv(cf_blast_output+'.csv',index=False,header=False)

def find_Homolog(INPUT_DATA_PATH,DATA_PATH,INPUT_QUERY_FASTA_FILE,INPUT_QUERY_NAME,INPUT_DF,input_seqtype,processes):
	'''
	For each cleaned_filename, blast for the query file and then retrieve all hits from the cleaned_filename.faa
	Step1: Get input directories
	Step2: Make parallel submission of cleaned_filenames from input_df to parallel_FindHomolog
	Output: .csv blast hits file, .txt fabv homolog sequences file
	'''
	seq_extension = read_SeqType(input_seqtype)
	##Step1
	prokka_input = pjoin(INPUT_DATA_PATH,'prokka_output')
	blast_input = pjoin(INPUT_DATA_PATH,'blast_output')
	blast_output = pjoin(DATA_PATH,'%s_blast_output'%INPUT_QUERY_NAME)
	#making blast_output path if it doesnt't exist
	if os.path.exists(blast_output) == False: os.mkdir(blast_output)
	##Step2
	#metadata with cleaned_filename
	df_metadata = pd.read_csv(pjoin(INPUT_DF))
	input_faa = df_metadata['cleaned_filename'].tolist()
	print('MESSAGE: searching %s genomes'%str(len(input_faa)))
	#parallel commands
	parallel_input = [[cf,INPUT_DATA_PATH,INPUT_QUERY_FASTA_FILE,prokka_input,blast_input,blast_output,seq_extension] for cf in input_faa]
	pool = Pool(processes = processes)
	pool.starmap(parallel_FindHomolog, parallel_input[:])
	pool.close()


def merge_BlastHomologOutputs(DATA_PATH,INPUT_QUERY_NAME,input_seqtype):
	'''
	blast_Homolog generates two outputs per cleaned_filename: a .faa/ffn file and a .csv file
	All faa/ffn files and all .csv files are concatenated
	Step1: concatenate faa/ffn files, Step2: concatenate .csv files, Step3: Fix hit.csv file and resave, Step4: remove temp blast_output
	'''
	seq_extension = read_SeqType(input_seqtype)
	#directory with output files to concatenate
	blast_output = pjoin(DATA_PATH,'%s_blast_output'%INPUT_QUERY_NAME)
	##Step1: Concatenating .txt files
	#list of all .txt output files
	all_homolog_seq_files = [pjoin(blast_output,x) for x in os.listdir(blast_output) if x.endswith(seq_extension)]
	#output filename
	concat_homolog_seqs = pjoin(DATA_PATH,'%s_homologs'%INPUT_QUERY_NAME)
	cat_Files(all_homolog_seq_files,seq_extension.replace('.',''),DATA_PATH,concat_homolog_seqs)
	##Step2:Concatenating .csv files
	#list of all .csv output files
	all_homolog_hit_files = [pjoin(blast_output,x) for x in os.listdir(blast_output) if x.endswith('.csv')]
	#output filename
	concat_blast_hits = pjoin(DATA_PATH,'%s_homologs'%INPUT_QUERY_NAME)
	cat_Files(all_homolog_hit_files,'csv',DATA_PATH,concat_blast_hits)
	##Step3:Reading in hit.csv file, adding in column names, and resaving under the same name
	col_names = ['sseqid','stitle','mismatch','positive','gaps','ppos','pident','qcovs','evalue','bitscore','qseqid','cleaned_filename']
	df_hits = pd.read_csv(concat_blast_hits+'.csv',names=col_names)
	df_hits.to_csv(concat_blast_hits+'.csv',index=False)
	##Step4:Removing temp_blast_output
	os.system('rm -R %s'%blast_output)



def run_GetHomologs(INPUT_DATA_PATH_,DATA_PATH_,INPUT_QUERY_FASTA_FILE_,INPUT_QUERY_NAME_,INPUT_DF_,input_seqtype,processes_):
	s = timer()
	get_GetHomologsPATHS(INPUT_DATA_PATH_,DATA_PATH_,INPUT_QUERY_FASTA_FILE_,INPUT_QUERY_NAME_,INPUT_DF_)
	print('find_Homolog')
	find_Homolog(INPUT_DATA_PATH,DATA_PATH,INPUT_QUERY_FASTA_FILE,INPUT_QUERY_NAME,INPUT_DF,input_seqtype,processes_,)
	print('merge_BlastHomologOutputs')
	merge_BlastHomologOutputs(DATA_PATH,INPUT_QUERY_NAME,input_seqtype)
	e = timer()
	print('total time:')
	print(e-s)








