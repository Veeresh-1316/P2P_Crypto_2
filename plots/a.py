import sys
from matplotlib import pyplot as plt
import numpy as np

NR = 1000
N = 100 
q = float(sys.argv[3]) #0.3
p = float(sys.argv[2]) #0.5
rate_factor = 1
mle = lambda trusts,score,round_number : (trusts*round_number + score)/(round_number+1)
momentum = lambda trusts,score,round_number :  trusts*rate_factor + (1-rate_factor)*score
algo = [ mle , momentum ][int(sys.argv[1]) - 1]
    
def correct(trusts,score) : 
    # t = np.maximum( trusts , np.ones(N)*0.001 )
    # t = t*(1+np.log(t)**2)
    t = (trusts*round_number + 1)/(round_number+1)
    t[score == 0] = 0  
    return t 

def wrong(trusts,score) : 
    # t = np.maximum( trusts - 0.02 , np.zeros(N) )
    t = (trusts*round_number)/(round_number+1)
    t[score == 1] = 0  
    return t 

round_number = 0 
n1 = round((1-q) * p * N)
n2 = round((1-q) * (1-p) * N )
n3 = N - (n1+n2)
probs = [(n1,0.9),(n2,0.7),(n3,0)]

def plot_stats(data : np.ndarray,func , fname  , ylabel ,title ) : 
    d1 = func( data[:,:n1]) 
    d2 = func( data[:,n1:n1+n2] ) 
    d3 = func( data[:,n1+n2:N] )
    plt.plot(d1,color="blue",label="Honest (0.9)")
    plt.plot(d2,color="green",label="Honest (0.7)")
    plt.plot(d3,color="red",label="Malicious")
    plt.xlabel('Time')
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True)
    plt.legend()
    plt.savefig(fname)
    plt.close()

trusts = np.ones(N) / 2 
data = trusts.reshape(1,N)

for _ in range(NR) : 
    votes = []
    for (n,prob) in probs : votes.append( np.random.choice(2,n,p=[ 1-prob , prob ]) )
    votes = np.concatenate(votes)
    result = int( np.sum(votes*trusts)/np.sum(trusts) >= 0.5)
    score = votes.copy()
    if result == 0 :  score = 1 - score
    trusts = momentum( trusts, score, round_number )
    data = np.vstack( (data , trusts.reshape(1,N)) )
    round_number += 1 

#print( data[:,:n1] )

plot_stats(data,lambda x : np.average(x,axis=1) , fname = f"{p}_{q}_avg.png" , ylabel="Average Trustworthiness" , title="") 
plot_stats(data,lambda x : np.std(x,axis=1) , fname = f"{p}_{q}_std.png" , ylabel="Standard Deviation" , title="") 

print( n1, n2 ,n3 )
print( 0.1*n1 + 0.3*n2 + n3 )
print( np.average(trusts[:n1]) )
print( np.average(trusts[n1:n1+n2]) )
print( np.average(trusts[n1+n2:]) )