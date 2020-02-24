## @ingroup Methods-Power-Battery-Charge
# datta_charge.py
# 
# Created:  

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------

import numpy as np

# ----------------------------------------------------------------------
#  Datta Discharge
# ----------------------------------------------------------------------

## @ingroup Methods-Power-Battery-Charge
def datta_charge(battery,numerics): 
    """models charge losses based on an empirical correlation
       Based on method taken from Datta and Johnson: 
       
       Assumptions: 
       Constant Peukart coefficient
       
       Source:
       "Requirements for a Hydrogen Powered All-Electric Manned Helicopter" by Datta and Johnson
      
       voltage model from from Chen, M. and Rincon-Mora, G. A., "Accurate Electrical Battery Model Capable of Predicting
       # Runtime and I - V Performance" IEEE Transactions on Energy Conversion, Vol. 21, No. 2, June 2006, pp. 504-511
       
       Inputs:
         battery. 
               I_bat             (max_energy)                          [Joules]
               cell_mass         (battery cell mass)                   [kilograms]
               Cp                (battery cell specific heat capacity) [J/(K kg)] 
               E_max             (max energy)                          [Joules]
               E_current         (current energy)                      [Joules]
               Q_prior           (charge throughput)                   [Amp-hrs]
               R_growth_factor   (internal resistance growth factor)   [unitless]
               E_growth_factor   (capactance (energy) growth factor)   [unitless] 
           
         inputs.
               I_bat             (current)                             [amps]
               P_bat             (power)                               [Watts]
       
       Outputs:
         battery.          
              current_energy                                           [Joules]
              cell_temperature                                         [Degrees Celcius]
              resistive_losses                                         [Watts] 
              load_power                                               [Watts]
              current                                                  [Amps]
              voltage_open_circuit                                     [Volts]
              battery_thevenin_voltage                                 [Volts]
              charge_throughput                                        [Amp-hrs]
              internal_resistance                                      [Ohms]
              state_of_charge                                          [unitless]
              depth_of_discharge                                       [unitless]
              voltage_under_load                                       [Volts]   
        
        
    """
    
    # Unpack varibles 
    I_bat             = battery.inputs.current
    P_bat             = battery.inputs.power_in  
    R_bat             = battery.resistance
    V_max             = battery.max_voltage
    bat_mass          = battery.mass_properties.mass                
    bat_Cp            = battery.specific_heat_capacity
    T_current         = battery.temperature
    E_max             = battery.max_energy
    E_current         = battery.current_energy 
    Q_prior           = battery.charge_throughput 
    R_growth_factor   = battery.R_growth_factor
    E_growth_factor   = battery.E_growth_factor 
    I                 = numerics.time.integrate
    D                 = numerics.time.differentiate      
     
    # Update battery capacitance (energy) with aging factor
    E_max = E_max*E_growth_factor
    
    # Compute state of charge and depth of discarge of the battery
    initial_discharge_state = np.dot(I,P_bat) + E_current[0]
    DOD_old =  1 - np.divide(initial_discharge_state,E_max)
    DOD_old[DOD_old< 0.] = 0. 
    
    # compute the C rate
    C = np.abs(3600.*P_bat/E_max)
    
    # Empirical for for discharge   
    f = 1-np.exp(-20.*DOD_old)-np.exp(-20.*(1.- DOD_old)) 
    f[f<0.0] = 0.0 # Negative f's don't make sense
    f = np.reshape(f, np.shape(C))
    
    # Compute internal resistance
    R_0 = R_bat*(1.+np.multiply(C,f))*R_growth_factor
    R_0[R_0==R_bat] = 0.  # when battery isn't being called
    
    # Compute Heat power generated by all cells
    P_heat = (I_bat**2.)*R_0
    
    # Determine actual power going into the battery accounting for resistance losses
    P = P_bat - np.abs(P_heat) 
    
    # Compute temperature rise of battery
    dT_dt     = P_heat /(bat_mass*bat_Cp)
    T_current = T_current[0] + np.dot(I,dT_dt)
    
    E_bat = np.dot(I,P)
    E_bat = np.reshape(E_bat,np.shape(E_current)) #make sure it's consistent
    
    # Add this to the current state
    if np.isnan(E_bat).any():
        E_bat=np.ones_like(E_bat)*np.max(E_bat)
        if np.isnan(E_bat.any()): #all nans; handle this instance
            E_bat=np.zeros_like(E_bat)
            
    E_current = E_bat + E_current[0]
    
    SOC_new = np.divide(E_current,E_max)
    SOC_new[SOC_new>1] = 1.
    SOC_new[SOC_new<0] = 0. 
    DOD_new = 1 - SOC_new
     
    # determine new charge throughput  
    Q_current = np.dot(I,abs(I_bat))
    Q_total   = Q_prior + Q_current[-1][0]/3600    
            
    # A voltage model from Chen, M. and Rincon-Mora, G. A., "Accurate Electrical Battery Model Capable of Predicting
    # Runtime and I - V Performance" IEEE Transactions on Energy Conversion, Vol. 21, No. 2, June 2006, pp. 504-511
    V_normalized  = (-1.031*np.exp(-35.*SOC_new) + 3.685 + 0.2156*SOC_new - 0.1178*(SOC_new**2.) + 0.3201*(SOC_new**3.))/4.1
    V_oc = V_normalized * V_max
    V_oc[ V_oc > V_max] = V_max
    
    # Voltage under load:
    V_ul   = V_oc + I_bat*R_0
        
    # Pack outputs
    battery.current_energy          = E_current
    battery.resistive_losses        = P_heat
    battery.cell_temperature        = T_current
    battery.load_power              = V_ul*I_bat
    battery.state_of_charge         = SOC_new 
    battery.depth_of_discharge      = DOD_new
    battery.charge_throughput       = Q_total
    battery.voltage_open_circuit    = V_oc
    battery.voltage_under_load      = V_ul
    battery.current                 = I_bat
    
    return